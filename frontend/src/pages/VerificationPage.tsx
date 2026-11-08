import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { BadgeCheck, Camera, Check, FileUp, ShieldCheck } from 'lucide-react';
import {
  EVIDENCE_MAX_BYTES,
  EVIDENCE_TYPES,
  getMyVerification,
  getVerificationDistricts,
  getVerificationInstitutions,
  issueLivenessChallenge,
  requestVerification,
  respondToVerification,
  saveVerificationStep,
  sendStudentEmailCode,
  sendVerificationPhoneCode,
  submitVerification,
  uploadEvidence,
  verifyStudentEmailCode,
  verifyVerificationPhoneCode,
  withdrawVerification,
} from '../api/account';
import { Notice, accountErrorMessage, linkClass, primaryButtonClass } from '../components/auth/AccountUi';
import { AccountNeedsConnection, LoadingState } from '../components/common/StatusViews';
import { SignInLink } from '../components/common/SignInLink';
import { useLanguage } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import type { VerificationEvidenceKind, VerificationMine, VerificationStep } from '../types';

const STEPS: { key: VerificationStep | 'review'; bn: string; en: string }[] = [
  { key: 'eligibility', bn: 'যোগ্যতা ও সম্মতি', en: 'Eligibility & consent' },
  { key: 'personal', bn: 'ব্যক্তিগত তথ্য', en: 'Personal details' },
  { key: 'phone', bn: 'ফোন যাচাই', en: 'Verify phone' },
  { key: 'document', bn: 'পরিচয়পত্র', en: 'Identity document' },
  { key: 'student', bn: 'শিক্ষার্থী পরিচয়', en: 'Student status' },
  { key: 'selfie', bn: 'লাইভ সেলফি', en: 'Live selfie' },
  { key: 'emergency', bn: 'জরুরি যোগাযোগ', en: 'Emergency contact' },
  { key: 'review', bn: 'পর্যালোচনা ও জমা', en: 'Review & submit' },
];
const OPEN = new Set(['draft', 'needs_clarification']);
const field = 'w-full rounded-xl border border-surface-muted/40 bg-white/70 dark:bg-dark-surface-2 px-3 py-2.5 text-sm';

function CameraCapture({ disabled, onCapture, label }: { disabled: boolean; onCapture: (blob: Blob) => void; label: string }) {
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => () => stream.current?.getTracks().forEach((track) => track.stop()), []);
  const start = async () => {
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
      if (video.current) video.current.srcObject = stream.current;
      setActive(true);
    } catch {
      setError('Camera permission is required. Open the site permissions in Chrome and allow Camera.');
    }
  };
  const snap = () => {
    const source = video.current;
    if (!source?.videoWidth) return;
    const canvas = document.createElement('canvas');
    canvas.width = source.videoWidth;
    canvas.height = source.videoHeight;
    canvas.getContext('2d')?.drawImage(source, 0, 0);
    canvas.toBlob((blob) => { if (blob) onCapture(blob); }, 'image/jpeg', 0.9);
  };
  return (
    <div className="flex flex-col gap-2">
      {active ? <video ref={video} autoPlay playsInline muted className="w-full max-h-80 rounded-2xl bg-black object-contain" /> : null}
      {!active ? (
        <button type="button" disabled={disabled} onClick={() => void start()} className={`${primaryButtonClass} px-5 self-start`}><Camera size={16} />{label}</button>
      ) : (
        <button type="button" disabled={disabled} onClick={snap} className={`${primaryButtonClass} px-5 self-start`}><Camera size={16} />Capture now</button>
      )}
      {error && <p className="text-sm text-error-alert">{error}</p>}
    </div>
  );
}

function FilePicker({ kind, busy, done, onFile }: { kind: VerificationEvidenceKind; busy: boolean; done: boolean; onFile: (kind: VerificationEvidenceKind, file: File) => void }) {
  return (
    <label className="flex items-center gap-2 rounded-xl border border-dashed border-forest-primary/50 px-4 py-3 cursor-pointer">
      {done ? <Check size={18} className="text-forest-primary" /> : <FileUp size={18} />}
      <span className="text-sm font-bold">{kind.replace('_', ' ')} {done ? '✓' : ''}</span>
      <input className="sr-only" type="file" accept={EVIDENCE_TYPES.join(',')} disabled={busy} onChange={(event) => {
        const file = event.target.files?.[0]; event.target.value = ''; if (file) onFile(kind, file);
      }} />
    </label>
  );
}

export const VerificationPage: React.FC = () => {
  const { t } = useLanguage();
  const { session, status, refresh } = useSession();
  const [data, setData] = useState<VerificationMine | null>(null);
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ tone: 'error' | 'success' | 'info'; text: string } | null>(null);
  const [districts, setDistricts] = useState<string[]>([]);
  const [institutions, setInstitutions] = useState<{ id: string; name_en: string; name_bn: string | null }[]>([]);
  const [personal, setPersonal] = useState({ legal_name_en: '', legal_name_bn: '', date_of_birth: '', gender: 'FEMALE', home_district: '', current_area: '', occupation: 'EMPLOYED' });
  const [phone, setPhone] = useState('');
  const [phoneCode, setPhoneCode] = useState('');
  const [doc, setDoc] = useState({ doc_type: 'NID', doc_number: '', doc_expiry: '' });
  const [student, setStudent] = useState({ institution_id: '', institution_other: '', study_end: '', email: '', code: '' });
  const [emergency, setEmergency] = useState({ name: '', relationship: '', phone: '', skip: false });
  const [declaration, setDeclaration] = useState(false);

  const load = useCallback(async () => {
    const mine = await getMyVerification();
    setData(mine);
    if (mine.case && OPEN.has(mine.case.state)) {
      const incomplete = STEPS.findIndex((item) => item.key !== 'review' && mine.case?.required_steps.includes(item.key) && !mine.case.steps[item.key]);
      setStep(incomplete < 0 ? 7 : incomplete);
    }
  }, []);
  useEffect(() => {
    if (session.kind !== 'member') return;
    void Promise.all([load(), getVerificationDistricts(), getVerificationInstitutions()])
      .then(([, districtData, institutionData]) => {
        setDistricts(districtData.divisions.flatMap((item) => item.districts));
        setInstitutions(institutionData.items);
      })
      .catch((error) => setNotice({ tone: 'error', text: accountErrorMessage(error, t) }));
  }, [session.kind, load, t]);

  const run = async (work: () => Promise<unknown>, success: string, advance = false) => {
    setBusy(true); setNotice(null);
    try {
      await work(); await load();
      setNotice({ tone: 'success', text: success });
      if (advance) setStep((value) => Math.min(value + 1, 7));
    } catch (error) {
      setNotice({ tone: 'error', text: accountErrorMessage(error, t) });
    } finally { setBusy(false); }
  };
  const current = data?.case;
  const upload = (kind: VerificationEvidenceKind, file: File | Blob, advance = false) => {
    if (!current) return;
    if (file.size > EVIDENCE_MAX_BYTES || !EVIDENCE_TYPES.includes(file.type || 'image/jpeg')) {
      setNotice({ tone: 'error', text: t('শুধু JPG/PNG, সর্বোচ্চ ৮ MB।', 'Use a JPG/PNG image up to 8 MB.') }); return;
    }
    void run(() => uploadEvidence(current.id, kind, file), t('ছবি নিরাপদে গ্রহণ করা হয়েছে।', 'Image securely received.'), advance);
  };

  if (status === 'loading') return <LoadingState />;
  if (status === 'unreachable') return <AccountNeedsConnection onRetry={() => void refresh()} />;
  if (session.kind !== 'member') return <div className="max-w-xl mx-auto p-8"><Notice tone="info">{t('আবেদনের জন্য আগে সাইন ইন করুন।', 'Sign in before applying.')} <SignInLink className={linkClass}>{t('সাইন ইন', 'Sign in')}</SignInLink></Notice></div>;

  if (data?.verified_member && (!current || !OPEN.has(current.state))) return (
    <main className="max-w-2xl mx-auto p-6 py-10 flex flex-col gap-5">
      <div className="tonal-card p-6 flex gap-3"><BadgeCheck size={30} className="text-forest-primary" /><div><h1 className="text-2xl font-bold">{t('আপনি যাচাইকৃত সদস্য', 'You are a Verified Member')}</h1><p>{t('Tours ও TourMates এখন আপনার জন্য খোলা।', 'Tours and TourMates are now available to you.')}</p></div></div>
      <Link to="/tours" className={`${primaryButtonClass} px-6 self-start`}>{t('আমার ট্যুর খুলুন', 'Open my tours')}</Link>
    </main>
  );

  if (!current || !OPEN.has(current.state)) return (
    <main className="max-w-2xl mx-auto p-6 py-10 flex flex-col gap-5">
      <ShieldCheck size={36} className="text-forest-primary" />
      <h1 className="text-3xl font-bold">{t('যাচাইকৃত সদস্য হোন', 'Become a Verified Member')}</h1>
      {notice && <Notice tone={notice.tone}>{notice.text}</Notice>}
      {!data?.email_verified && <Notice tone="error">{t('প্রথমে আপনার ইমেইল যাচাই করুন।', 'Verify your email first.')}</Notice>}
      {data?.cooldown_until && <Notice tone="info">{t('পুনরায় আবেদনের সময়: ', 'You can apply again after: ')}{new Date(data.cooldown_until).toLocaleString()}</Notice>}
      {data?.banned_until && <Notice tone="error">{t('আপনার যাচাইকরণ আবেদন সীমাবদ্ধ।', 'Your verification applications are restricted.')}</Notice>}
      {current && <Notice tone="info">{t('সর্বশেষ অবস্থা: ', 'Latest status: ')}{current.state}{current.decision_reason ? ` — ${t(current.decision_reason.bn, current.decision_reason.en)}` : ''}</Notice>}
      {current?.state === 'rejected' && <Link to="/account/appeals" className={linkClass}>{t('সিদ্ধান্তের বিরুদ্ধে আপিল করুন', 'Appeal this decision')}</Link>}
      <button type="button" disabled={busy || !data?.email_verified || Boolean(data?.cooldown_until || data?.banned_until)} onClick={() => void run(() => requestVerification(data?.verification?.state === 'renewal_due' ? 'renewal' : 'initial'), t('খসড়া শুরু হয়েছে।', 'Application started.'))} className={`${primaryButtonClass} px-6 self-start`}>{t('আবেদন শুরু করুন', 'Start application')}</button>
    </main>
  );

  const visibleSteps = STEPS.filter((item) => item.key !== 'student' || current.required_steps.includes('student'));
  const active = STEPS[step]?.key;
  return (
    <main className="max-w-3xl mx-auto p-4 sm:p-6 py-8 flex flex-col gap-5">
      <div><h1 className="text-2xl font-bold">{t('যাচাইকৃত সদস্য আবেদন', 'Verified Member application')}</h1><p className="text-sm text-on-surface-variant">{t('খসড়া স্বয়ংক্রিয়ভাবে সংরক্ষিত হয়। পরিচয়পত্র শুধু অনুমোদিত পর্যালোচক দেখবেন।', 'Your draft is saved after every step. Identity images are visible only to authorised reviewers.')}</p></div>
      <ol className="flex gap-2 overflow-x-auto pb-2" aria-label="Application progress">
        {visibleSteps.map((item) => { const index = STEPS.findIndex((candidate) => candidate.key === item.key); const done = item.key !== 'review' && current.steps[item.key]; return <li key={item.key}><button type="button" onClick={() => setStep(index)} className={`whitespace-nowrap rounded-full px-3 py-2 text-xs font-bold ${index === step ? 'bg-forest-primary text-white' : 'bg-surface-container'}`}>{done ? '✓ ' : ''}{t(item.bn, item.en)}</button></li>; })}
      </ol>
      {notice && <Notice tone={notice.tone}>{notice.text}</Notice>}

      <section className="tonal-card p-5 sm:p-6 flex flex-col gap-4">
        {active === 'eligibility' && <>
          <h2 className="text-xl font-bold">{t('যোগ্যতা ও সম্মতি', 'Eligibility & consent')}</h2>
          <p>{t('আবেদনকারীর বয়স কমপক্ষে ১৮ বছর হতে হবে। তথ্য পরিচয় যাচাই ও নিরাপদ TourMates ব্যবহারের জন্য প্রক্রিয়া করা হবে।', 'You must be at least 18. Your information is processed for identity verification and safer TourMates access.')}</p>
          <button disabled={busy} className={`${primaryButtonClass} px-5 self-start`} onClick={() => void run(() => saveVerificationStep(current.id, 'eligibility', { age_confirmed: true, consent: true }), t('সম্মতি সংরক্ষিত।', 'Consent saved.'), true)}>{t('আমি ১৮+ এবং সম্মত', 'I am 18+ and consent')}</button>
        </>}

        {active === 'personal' && <>
          <h2 className="text-xl font-bold">{t('ব্যক্তিগত তথ্য', 'Personal details')}</h2>
          <input className={field} placeholder="Legal name in English" value={personal.legal_name_en} onChange={(e) => setPersonal({ ...personal, legal_name_en: e.target.value })} />
          <input className={field} placeholder="বাংলায় নাম (ঐচ্ছিক)" value={personal.legal_name_bn} onChange={(e) => setPersonal({ ...personal, legal_name_bn: e.target.value })} />
          <label className="text-sm font-bold">{t('জন্মতারিখ', 'Date of birth')}<input className={`${field} mt-1`} type="date" value={personal.date_of_birth} onChange={(e) => setPersonal({ ...personal, date_of_birth: e.target.value })} /></label>
          <select className={field} value={personal.gender} onChange={(e) => setPersonal({ ...personal, gender: e.target.value })}><option value="FEMALE">Female</option><option value="MALE">Male</option><option value="THIRD">Third gender</option></select>
          <select className={field} value={personal.home_district} onChange={(e) => setPersonal({ ...personal, home_district: e.target.value })}><option value="">Home district</option>{districts.map((name) => <option key={name}>{name}</option>)}</select>
          <input className={field} placeholder="Current area (optional)" value={personal.current_area} onChange={(e) => setPersonal({ ...personal, current_area: e.target.value })} />
          <select className={field} value={personal.occupation} onChange={(e) => setPersonal({ ...personal, occupation: e.target.value })}><option value="STUDENT">Student</option><option value="EMPLOYED">Employed</option><option value="SELF_EMPLOYED">Self-employed</option><option value="NOT_WORKING">Not working</option><option value="OTHER">Other</option></select>
          <button disabled={busy} className={`${primaryButtonClass} px-5 self-start`} onClick={() => void run(() => saveVerificationStep(current.id, 'personal', personal), t('ব্যক্তিগত তথ্য সংরক্ষিত।', 'Personal details saved.'), true)}>{t('সংরক্ষণ ও পরবর্তী', 'Save and continue')}</button>
        </>}

        {active === 'phone' && <>
          <h2 className="text-xl font-bold">{t('ফোন যাচাই', 'Verify phone')}</h2>
          {current.phone?.verified ? <Notice tone="success">•••• {current.phone.last4} verified</Notice> : <><input className={field} inputMode="tel" placeholder="01XXXXXXXXX" value={phone} onChange={(e) => setPhone(e.target.value)} /><button disabled={busy || !phone} className={`${primaryButtonClass} px-5 self-start`} onClick={() => void run(() => sendVerificationPhoneCode(current.id, phone), t('কোড পাঠানো হয়েছে।', 'Code sent.'))}>{t('কোড পাঠান', 'Send code')}</button><input className={field} inputMode="numeric" maxLength={6} placeholder="6-digit code" value={phoneCode} onChange={(e) => setPhoneCode(e.target.value.replace(/\D/g, ''))} /><button disabled={busy || phoneCode.length !== 6} className={`${primaryButtonClass} px-5 self-start`} onClick={() => void run(() => verifyVerificationPhoneCode(current.id, phoneCode), t('ফোন যাচাই হয়েছে।', 'Phone verified.'), true)}>{t('যাচাই করুন', 'Verify')}</button></>}
        </>}

        {active === 'document' && <>
          <h2 className="text-xl font-bold">{t('পরিচয়পত্র', 'Identity document')}</h2>
          <select className={field} value={doc.doc_type} onChange={(e) => setDoc({ ...doc, doc_type: e.target.value })}><option value="NID">National ID</option><option value="PASSPORT">Passport</option><option value="DRIVING_LICENCE">Driving licence</option></select>
          <input className={field} placeholder="Document number" value={doc.doc_number} onChange={(e) => setDoc({ ...doc, doc_number: e.target.value })} />
          {(doc.doc_type === 'PASSPORT' || doc.doc_type === 'DRIVING_LICENCE') && <label className="text-sm font-bold">Expiry date<input className={`${field} mt-1`} type="date" value={doc.doc_expiry} onChange={(e) => setDoc({ ...doc, doc_expiry: e.target.value })} /></label>}
          <button disabled={busy || !doc.doc_number} className={`${primaryButtonClass} px-5 self-start`} onClick={() => void run(() => saveVerificationStep(current.id, 'document', { ...doc, doc_expiry: doc.doc_expiry || null }), t('পরিচয়পত্রের তথ্য সংরক্ষিত।', 'Document details saved.'))}>{t('তথ্য সংরক্ষণ', 'Save details')}</button>
          <FilePicker kind="DOC_FRONT" busy={busy} done={Boolean(current.evidence.DOC_FRONT)} onFile={upload} />
          {(doc.doc_type === 'NID' || doc.doc_type === 'DRIVING_LICENCE') && <FilePicker kind="DOC_BACK" busy={busy} done={Boolean(current.evidence.DOC_BACK)} onFile={(kind, file) => upload(kind, file, true)} />}
          {doc.doc_type === 'PASSPORT' && current.evidence.DOC_FRONT && <button type="button" className={`${primaryButtonClass} px-5 self-start`} onClick={() => setStep(step + 1)}>{t('পরবর্তী', 'Continue')}</button>}
        </>}

        {active === 'student' && <>
          <h2 className="text-xl font-bold">{t('শিক্ষার্থী পরিচয়', 'Student status')}</h2>
          <select className={field} value={student.institution_id} onChange={(e) => setStudent({ ...student, institution_id: e.target.value })}><option value="">Choose institution</option>{institutions.map((item) => <option key={item.id} value={item.id}>{item.name_en}</option>)}</select>
          {!student.institution_id && <input className={field} placeholder="Other institution" value={student.institution_other} onChange={(e) => setStudent({ ...student, institution_other: e.target.value })} />}
          <label className="text-sm font-bold">Study ends<input className={`${field} mt-1`} type="month" value={student.study_end} onChange={(e) => setStudent({ ...student, study_end: e.target.value })} /></label>
          <button disabled={busy} className={`${primaryButtonClass} px-5 self-start`} onClick={() => void run(() => saveVerificationStep(current.id, 'student', student), t('শিক্ষার্থী তথ্য সংরক্ষিত।', 'Student details saved.'))}>Save details</button>
          <FilePicker kind="STUDENT_CARD" busy={busy} done={Boolean(current.evidence.STUDENT_CARD)} onFile={upload} />
          <input className={field} type="email" placeholder="Academic email (optional)" value={student.email} onChange={(e) => setStudent({ ...student, email: e.target.value })} /><button disabled={busy || !student.email} className={`${primaryButtonClass} px-5 self-start`} onClick={() => void run(() => sendStudentEmailCode(current.id, student.email), 'Academic email code sent.')}>Send email code</button>
          <input className={field} inputMode="numeric" maxLength={6} placeholder="Email code (optional)" value={student.code} onChange={(e) => setStudent({ ...student, code: e.target.value.replace(/\D/g, '') })} /><button disabled={busy || student.code.length !== 6} className={`${primaryButtonClass} px-5 self-start`} onClick={() => void run(() => verifyStudentEmailCode(current.id, student.code), 'Academic email verified.', true)}>Verify and continue</button>
          {current.evidence.STUDENT_CARD && <button type="button" className={linkClass} onClick={() => setStep(step + 1)}>Continue without academic email</button>}
        </>}

        {active === 'selfie' && <>
          <h2 className="text-xl font-bold">{t('লাইভ সেলফি', 'Live selfie')}</h2>
          {!current.liveness && <button disabled={busy} className={`${primaryButtonClass} px-5 self-start`} onClick={() => void run(() => issueLivenessChallenge(current.id), t('লাইভ নির্দেশনা তৈরি হয়েছে।', 'Live challenge ready.'))}>{t('ক্যামেরা ধাপ শুরু করুন', 'Start camera step')}</button>}
          {current.liveness && <Notice tone="info"><strong>{current.liveness.code}</strong> — {t(current.liveness.gesture_bn, current.liveness.gesture_en)}. {t('কোডটি কাগজে লিখে নির্দেশিত ভঙ্গিসহ ছবি তুলুন।', 'Write the code on paper and take the photo while making the requested gesture.')}</Notice>}
          {current.liveness && <CameraCapture disabled={busy} label={t('ক্যামেরা চালু করুন', 'Open camera')} onCapture={(blob) => upload('SELFIE', blob, true)} />}
        </>}

        {active === 'emergency' && <>
          <h2 className="text-xl font-bold">{t('জরুরি যোগাযোগ (ঐচ্ছিক)', 'Emergency contact (optional)')}</h2>
          <p className="text-sm">{t('ট্যুর নিশ্চিত হলে এই যোগাযোগটি Safety মডিউলে কপি করা যাবে।', 'This contact can be copied to the Safety module when a tour is confirmed.')}</p>
          <input className={field} placeholder="Contact name" value={emergency.name} onChange={(e) => setEmergency({ ...emergency, name: e.target.value, skip: false })} /><input className={field} placeholder="Relationship" value={emergency.relationship} onChange={(e) => setEmergency({ ...emergency, relationship: e.target.value, skip: false })} /><input className={field} placeholder="Phone" value={emergency.phone} onChange={(e) => setEmergency({ ...emergency, phone: e.target.value, skip: false })} />
          <button disabled={busy} className={`${primaryButtonClass} px-5 self-start`} onClick={() => void run(() => saveVerificationStep(current.id, 'emergency', emergency.name ? emergency : { skip: true }), t('জরুরি যোগাযোগ ধাপ সম্পন্ন।', 'Emergency contact step complete.'), true)}>{emergency.name ? t('সংরক্ষণ ও পরবর্তী', 'Save and continue') : t('এখন বাদ দিন', 'Skip for now')}</button>
        </>}

        {active === 'review' && <>
          <h2 className="text-xl font-bold">{t('পর্যালোচনা ও জমা', 'Review & submit')}</h2>
          <ul className="text-sm grid sm:grid-cols-2 gap-2">{current.required_steps.map((name) => <li key={name} className="flex gap-2"><span>{current.steps[name] ? '✓' : '○'}</span>{name}</li>)}</ul>
          {current.decision_note && <Notice tone="info">{current.decision_note}</Notice>}
          <label className="flex gap-3 items-start"><input type="checkbox" checked={declaration} onChange={(e) => setDeclaration(e.target.checked)} /><span>{t('আমি ঘোষণা করছি যে তথ্য ও ছবি আমার নিজের এবং সত্য।', 'I declare that the information and images are mine and accurate.')}</span></label>
          <button disabled={busy || !declaration || current.required_steps.some((name) => !current.steps[name])} className={`${primaryButtonClass} px-6 self-start`} onClick={() => void run(() => current.state === 'needs_clarification' ? respondToVerification(current.id) : submitVerification(current.id, declaration), t('আবেদন জমা হয়েছে।', 'Application submitted.'))}>{current.state === 'needs_clarification' ? t('উত্তর জমা দিন', 'Submit clarification') : t('আবেদন জমা দিন', 'Submit application')}</button>
        </>}
      </section>
      <button type="button" disabled={busy} className="text-sm text-error-alert self-start" onClick={() => void run(() => withdrawVerification(current.id), t('আবেদন প্রত্যাহার করা হয়েছে।', 'Application withdrawn.'))}>{t('খসড়া/আবেদন প্রত্যাহার', 'Withdraw application')}</button>
    </main>
  );
};
