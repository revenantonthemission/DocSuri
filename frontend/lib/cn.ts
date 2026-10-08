import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// cn — conditional className composition (team mandate: clsx + tailwind-merge).
// clsx handles conditional truthiness; twMerge resolves conflicting Tailwind
// utility classes so a caller's later class wins over a component default.
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
