import React from 'react';
import { LogOut, Trash2 } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import { formatNumber } from '../../utils/format';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';

/**
 * The sign-out question for a member with unsent review drafts (guideline 6.7). Loaded only when it is
 * needed, so the dialog code stays out of the first download.
 */
const SignOutDraftsDialog: React.FC<{ count: number; busy: boolean; onCancel: () => void; onChoose: (removeDrafts: boolean) => void }> = ({
  count,
  busy,
  onCancel,
  onChoose,
}) => {
  const { t, language } = useLanguage();
  const n = formatNumber(count, language);
  return (
    <Dialog open onOpenChange={(open) => !open && !busy && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t(`${n}টি না পাঠানো রিভিউ খসড়া আছে`, `You have ${n} unsent review draft${count === 1 ? '' : 's'}`)}</DialogTitle>
          <DialogDescription>
            {t(
              'রেখে দিলে খসড়াগুলো এই ডিভাইসে থাকবে এবং আবার একই অ্যাকাউন্টে সাইন ইন করলেই দেখা যাবে; অন্য কেউ দেখতে পাবে না। মুছে দিলে ফেরানো যাবে না।',
              'If you keep them, they stay on this device and show again only when you sign in to this account; nobody else sees them. Deleting cannot be undone.',
            )}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex-wrap gap-2">
          <Button type="button" variant="outline" disabled={busy} onClick={onCancel}>
            {t('বাতিল', 'Cancel')}
          </Button>
          <Button type="button" variant="destructive" disabled={busy} onClick={() => onChoose(true)}>
            <Trash2 aria-hidden="true" />
            {t('খসড়া মুছে সাইন আউট', 'Delete drafts and sign out')}
          </Button>
          <Button type="button" disabled={busy} onClick={() => onChoose(false)}>
            <LogOut aria-hidden="true" />
            {t('খসড়া রেখে সাইন আউট', 'Keep drafts and sign out')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SignOutDraftsDialog;
