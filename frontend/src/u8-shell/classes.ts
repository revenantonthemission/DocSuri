/**
 * Class-name composition for the complete workspace (team rule: `clsx` + `tailwind-merge`).
 */
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cx(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
