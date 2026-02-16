import { useState, useRef, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import type { Operation } from '../types/api';

interface OperationsDropdownProps {
  onSelect: (operation: Operation) => void;
}

export default function OperationsDropdown({ onSelect }: OperationsDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (operation: Operation) => {
    setIsOpen(false);
    onSelect(operation);
  };

  return (
    <div ref={dropdownRef} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="px-2 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50 transition-colors flex items-center gap-1"
      >
        その他
        <ChevronDown className="w-3 h-3" />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-1 w-40 bg-white border border-gray-200 rounded-lg shadow-lg z-10">
          <button
            onClick={() => handleSelect('ADJUST')}
            className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors"
          >
            調整
          </button>
          <button
            onClick={() => handleSelect('RESERVE')}
            className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors"
          >
            引当
          </button>
          <button
            onClick={() => handleSelect('UNRESERVE')}
            className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors"
          >
            引当解除
          </button>
          <div className="border-t border-gray-200 my-1"></div>
          <button
            onClick={() => handleSelect('RETURN_ARRIVAL')}
            className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors"
          >
            返品到着
          </button>
          <button
            onClick={() => handleSelect('RETURN_APPROVE')}
            className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors"
          >
            検品OK
          </button>
          <button
            onClick={() => handleSelect('RETURN_REJECT')}
            className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors"
          >
            検品NG
          </button>
        </div>
      )}
    </div>
  );
}
