import { describe, expect, it } from 'vitest';
import { problemMessage } from './AccountUi';

const english = (_bn: string, en: string) => en;
const bangla = (bn: string) => bn;

describe('problemMessage: a password found in a data breach', () => {
  it('names the problem in the reader language, not the generic letter-and-digit rule', () => {
    expect(problemMessage('password', 'BREACHED', english)).toBe('This password appears in a known data breach. Choose a different one.');
    expect(problemMessage('password', 'BREACHED', bangla)).toContain('পাসওয়ার্ড');
    expect(problemMessage('password', 'WEAK', english)).not.toContain('breach');
  });
});
