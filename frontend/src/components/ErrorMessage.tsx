import { AlertTriangle } from 'lucide-react';

interface Props {
  message: string;
  onRetry?: () => void;
}

export default function ErrorMessage({ message, onRetry }: Props) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 flex items-center gap-3">
      <AlertTriangle className="w-5 h-5 text-red-500 shrink-0" />
      <p className="text-sm text-red-700 flex-1">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-sm font-medium text-red-600 hover:text-red-800 cursor-pointer"
        >
          再試行
        </button>
      )}
    </div>
  );
}
