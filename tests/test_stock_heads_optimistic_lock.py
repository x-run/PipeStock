"""stock_heads optimistic lock tests.

DB-direct tests that verify version increment and conflict detection.
"""

from unittest.mock import patch

from sqlalchemy import create_engine, event, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import InventoryTx, Item, StockHead
from app.schemas import TxCreate
from app.stock import calc_stock, create_txs


def _make_db():
    """Create an in-memory SQLite engine+session for direct DB tests."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _pragma(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=eng)
    return sessionmaker(bind=eng)


def _seed_item(db, code="LOCK-001"):
    """Create an item + stock_head and return the item."""
    item = Item(code=code, name="Lock test", unit="本",
                unit_price=100, reorder_point=0)
    db.add(item)
    db.flush()
    db.add(StockHead(item_id=item.id))
    db.commit()
    db.refresh(item)
    return item


def _concurrent_calc_stock(original_fn):
    """Return a calc_stock replacement that bumps version mid-flight."""
    def wrapper(db_session, item_id):
        result = original_fn(db_session, item_id)
        db_session.execute(
            update(StockHead)
            .where(StockHead.item_id == item_id)
            .values(version=StockHead.version + 1)
        )
        db_session.flush()
        return result
    return wrapper


class TestStockHeadsOptimisticLock:
    """Verify stock_heads version-based optimistic locking (DB-direct)."""

    def test_version_starts_at_zero(self):
        """Newly created stock_head has version=0."""
        Session = _make_db()
        db = Session()
        item = _seed_item(db)

        sh = db.query(StockHead).filter(StockHead.item_id == item.id).first()
        assert sh.version == 0
        db.close()

    def test_version_increments_per_tx_call(self):
        """Each create_txs call bumps stock_heads.version by exactly 1."""
        Session = _make_db()
        db = Session()
        item = _seed_item(db)

        create_txs(db, item, [TxCreate(type="IN", qty=100)])
        sh = db.query(StockHead).filter(StockHead.item_id == item.id).first()
        assert sh.version == 1

        create_txs(db, item, [TxCreate(type="OUT", qty=10)])
        db.expire_all()
        sh = db.query(StockHead).filter(StockHead.item_id == item.id).first()
        assert sh.version == 2

        create_txs(db, item, [TxCreate(type="RESERVE", qty=5)])
        db.expire_all()
        sh = db.query(StockHead).filter(StockHead.item_id == item.id).first()
        assert sh.version == 3

        db.close()

    def test_batch_bumps_version_once(self):
        """A batch create_txs call bumps version by 1 (not per-tx)."""
        Session = _make_db()
        db = Session()
        item = _seed_item(db)

        create_txs(db, item, [TxCreate(type="IN", qty=100)])
        create_txs(db, item, [
            TxCreate(type="OUT", qty=10),
            TxCreate(type="RESERVE", qty=5),
        ])
        db.expire_all()
        sh = db.query(StockHead).filter(StockHead.item_id == item.id).first()
        assert sh.version == 2  # 2 calls, not 3 txs
        db.close()

    def test_concurrent_conflict_returns_409(self):
        """Simulate stale version → 409 CONFLICT."""
        Session = _make_db()
        db = Session()
        item = _seed_item(db)

        create_txs(db, item, [TxCreate(type="IN", qty=100)])

        sh = db.query(StockHead).filter(StockHead.item_id == item.id).first()
        assert sh.version == 1

        with patch("app.stock.calc_stock",
                    side_effect=_concurrent_calc_stock(calc_stock)):
            try:
                create_txs(db, item, [TxCreate(type="OUT", qty=10)])
                assert False, "Should have raised AppError CONFLICT"
            except Exception as e:
                assert e.code == "CONFLICT"
                assert e.status_code == 409

        db.rollback()
        db.close()

    def test_conflict_does_not_persist_tx(self):
        """After CONFLICT, no inventory_tx rows from the failed attempt exist."""
        Session = _make_db()
        db = Session()
        item = _seed_item(db)

        create_txs(db, item, [TxCreate(type="IN", qty=50)])

        count_before = db.query(InventoryTx).filter(
            InventoryTx.item_id == item.id
        ).count()
        assert count_before == 1

        with patch("app.stock.calc_stock",
                    side_effect=_concurrent_calc_stock(calc_stock)):
            try:
                create_txs(db, item, [TxCreate(type="OUT", qty=10)])
            except Exception:
                pass

        db.rollback()

        count_after = db.query(InventoryTx).filter(
            InventoryTx.item_id == item.id
        ).count()
        assert count_after == count_before

        stock = calc_stock(db, item.id)
        assert stock.on_hand == 50
        db.close()

    def test_conflict_does_not_bump_version(self):
        """After CONFLICT, stock_heads.version stays at pre-conflict value."""
        Session = _make_db()
        db = Session()
        item = _seed_item(db)

        create_txs(db, item, [TxCreate(type="IN", qty=50)])
        # version is now 1 + 1 from concurrent bump = 2

        with patch("app.stock.calc_stock",
                    side_effect=_concurrent_calc_stock(calc_stock)):
            try:
                create_txs(db, item, [TxCreate(type="OUT", qty=10)])
            except Exception:
                pass

        db.rollback()
        db.expire_all()

        sh = db.query(StockHead).filter(StockHead.item_id == item.id).first()
        # After rollback, the concurrent bump is also rolled back.
        # The committed version from the first create_txs is 1.
        assert sh.version == 1
        db.close()
