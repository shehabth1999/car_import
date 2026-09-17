import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Head, usePage } from '@inertiajs/react';
import Button from '@/components/Base/Button';
import Lucide from '@/components/Base/Lucide';
import toast from '@/utils/toast';

declare const window: Window & { axios: any };

/**
 * The calculator, compact: one strip of inputs, two dense ledgers under it.
 * Every change posts to /car-import/calculator/compute/, which runs
 * `Quote._live_values()` — the quotation form's own engine. Nothing here
 * computes a price.
 */

type Choice = [string, string];

interface Props {
  shipping_types: Choice[];
  ports: Choice[];
  fx_rate: number | '';
  fx_note: string;
  can_save: boolean;
  forbidden?: boolean;
}

interface Result {
  band_label: string; net_eur: number; vat_reclaimable_eur: number; shipping_eur: number;
  admin_fee_before_discount_eur: number; admin_fee_eur: number; eur1_eur: number; shipping_extra_eur: number;
  total_eur: number; deposit_pct: number; deposit_eur: number; balance_eur: number;
  port_fee_egp: number; showroom_fee_egp: number; egp_due_on_arrival: number;
  total_egp_indicative: number | null; pricing_error: string;
}

interface Inputs {
  gross_price_eur: string; vat_rate_pct: string; with_eur1: boolean;
  shipping_type: '' | 'vip_roro' | 'container'; port: 'alexandria' | 'port_said';
  collect_from_showroom: boolean; admin_fee_discount_eur: string; fx_rate_egp: string;
}

const fmt = new Intl.NumberFormat('en-EG', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money = (n: number | null | undefined) => (n === null || n === undefined ? '—' : fmt.format(Math.abs(Number(n))));
const SHIPPING_LABEL: Record<string, string> = { standard: 'عادي', vip_roro: 'VIP RORO', container: 'كونتينر' };
const PORT_LABEL: Record<string, string> = { alexandria: 'الإسكندرية', port_said: 'بورسعيد' };

/* ── controls ─────────────────────────────────────────────────────────── */

function Field({ label, children, className = '' }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`flex flex-col gap-0.5 ${className}`}>
      <span className="text-[11px] leading-none text-slate-500">{label}</span>
      {children}
    </div>
  );
}

function Segmented<V extends string>({ options, value, onChange, label }:
  { options: Choice[]; value: V; onChange: (v: V) => void; label: string }) {
  return (
    <div role="group" aria-label={label} className="inline-flex h-8 rounded-md border border-slate-300 overflow-hidden">
      {options.map(([key, text]) => {
        const on = key === value;
        return (
          <button key={key} type="button" aria-pressed={on} onClick={() => onChange(key as V)}
            className={`px-2.5 text-[12.5px] border-e last:border-e-0 border-slate-300 focus:outline-none focus-visible:ring-2 ring-slate-400 ${on ? 'bg-slate-800 text-white' : 'bg-white text-slate-700 hover:bg-slate-50'}`}>
            {text}
          </button>
        );
      })}
    </div>
  );
}

function Check({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} onClick={() => onChange(!on)}
      className={`h-8 inline-flex items-center gap-1.5 rounded-md border px-2.5 text-[12.5px] focus:outline-none focus-visible:ring-2 ring-slate-400 ${on ? 'bg-emerald-700 border-emerald-700 text-white' : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'}`}>
      <Lucide icon={on ? 'CheckSquare' : 'Square'} className="w-3.5 h-3.5" />{label}
    </button>
  );
}

const NUM = 'h-8 w-24 rounded-md border border-slate-300 bg-white px-2 font-mono text-[13px] text-left focus:outline-none focus:ring-2 ring-slate-400';

/* ── ledger row ────────────────────────────────────────────────────────── */

function Ln({ k, v, neg, sum, tone }: { k: React.ReactNode; v: number | null | undefined; neg?: boolean; sum?: boolean; tone: 'eur' | 'egp' }) {
  const bg = sum ? (tone === 'eur' ? 'bg-emerald-50' : 'bg-orange-50') : '';
  return (
    <tr className={`border-t border-slate-100 ${bg} ${sum ? 'font-bold' : ''}`}>
      <td className="py-1 px-2 text-slate-700">{k}</td>
      <td dir="ltr" className={`py-1 px-2 text-right font-mono tabular-nums ${neg ? 'text-slate-400' : ''} ${sum ? 'text-[15px]' : ''}`}>
        {neg ? '− ' : ''}{money(v)}
      </td>
    </tr>
  );
}

/* ── page ─────────────────────────────────────────────────────────────── */

export default function Calculator() {
  const { props } = usePage();
  const { shipping_types, ports, fx_rate, fx_note, can_save, forbidden } = props as unknown as Props;

  const [inputs, setInputs] = useState<Inputs>({
    gross_price_eur: '', vat_rate_pct: '19', with_eur1: false, shipping_type: '', port: 'alexandria',
    collect_from_showroom: false, admin_fee_discount_eur: '', fx_rate_egp: fx_rate === '' ? '' : String(fx_rate),
  });
  const [more, setMore] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const inflight = useRef(0);
  const set = <K extends keyof Inputs>(key: K, value: Inputs[K]) => setInputs(s => ({ ...s, [key]: value }));

  useEffect(() => {
    if (!inputs.gross_price_eur) { setResult(null); setError(''); return; }
    const mine = ++inflight.current;
    const t = setTimeout(async () => {
      try {
        const r = await window.axios.post('/car-import/calculator/compute/', { ...inputs, admin_fee_discount_eur: inputs.admin_fee_discount_eur || 0 });
        if (mine !== inflight.current) return;
        setResult(r.data?.value); setError(r.data?.value?.pricing_error || '');
      } catch (e: any) {
        if (mine !== inflight.current) return;
        setResult(null); setError(e?.response?.data?.error || 'الحساب ما رجعش من السيرفر');
      }
    }, 200);
    return () => clearTimeout(t);
  }, [inputs]);

  const has = !!result && Number(result.total_eur) > 0;
  const discount = useMemo(() => (result ? Number(result.admin_fee_before_discount_eur) - Number(result.admin_fee_eur) : 0), [result]);

  const copy = useCallback(() => {
    if (!result) return;
    const L = (k: string, n: number, cur = '€') => `${k}: ${fmt.format(Number(n))} ${cur}`;
    const text = [
      `عرض سعر — ${result.band_label}`, L('سعر الإعلان', Number(inputs.gross_price_eur)), L('صافي', result.net_eur),
      L('الشحن', result.shipping_eur), L('المصاريف الإدارية', result.admin_fee_eur),
      Number(result.eur1_eur) > 0 ? L('EUR 1', result.eur1_eur) : null,
      Number(result.shipping_extra_eur) > 0 ? L('إضافة الشحن', result.shipping_extra_eur) : null,
      L('الإجمالي', result.total_eur), L('الوديعة', result.deposit_eur), L('الباقي', result.balance_eur),
      L('عند الوصول', result.egp_due_on_arrival, 'ج.م'),
    ].filter(Boolean).join('\n');
    navigator.clipboard.writeText(text).then(() => toast.success('اتنسخت'), () => toast.error('المتصفح ما سمحش بالنسخ'));
  }, [result, inputs.gross_price_eur]);

  const save = useCallback(async () => {
    setSaving(true);
    try {
      const r = await window.axios.post('/car-import/calculator/save/', { ...inputs, admin_fee_discount_eur: inputs.admin_fee_discount_eur || 0 });
      toast.success(`اتحفظ ${r.data?.name || ''}`);
      window.location.href = r.data.url;
    } catch (e: any) { setError(e?.response?.data?.error || 'ما اتحفظش'); setSaving(false); }
  }, [inputs]);

  if (forbidden) {
    return <div dir="rtl" className="p-4 text-slate-500 text-sm">الآلة الحاسبة لفريق المبيعات. اطلب من مدير المبيعات يضيفك للمجموعة.</div>;
  }

  return (
    <div dir="rtl" className="p-3 text-[13px] text-slate-800">
      <Head title="الآلة الحاسبة" />
      <div className="rounded-lg border border-slate-200 bg-white">

        {/* ── input strip ─────────────────────────────────────────── */}
        <div className="flex flex-wrap items-end gap-x-4 gap-y-2 px-3 py-2.5 border-b border-slate-200">
          <Field label="سعر الإعلان شامل الضريبة (€)">
            <input inputMode="decimal" autoFocus autoComplete="off" placeholder="48001" dir="ltr"
              value={inputs.gross_price_eur} onChange={e => set('gross_price_eur', e.target.value.replace(/[^\d.]/g, ''))}
              className="h-9 w-36 rounded-md border border-slate-300 bg-white px-2 font-mono text-[17px] font-semibold text-left focus:outline-none focus:ring-2 ring-slate-400" />
          </Field>
          <Field label="الشحن">
            <Segmented label="نوع الشحن" value={(inputs.shipping_type || 'standard') as any}
              options={shipping_types.map(([k]) => [k, SHIPPING_LABEL[k] || k])}
              onChange={v => set('shipping_type', (v === 'standard' ? '' : v) as Inputs['shipping_type'])} />
          </Field>
          <Field label="الميناء">
            <Segmented label="الميناء" value={inputs.port} options={ports.map(([k]) => [k, PORT_LABEL[k] || k])} onChange={v => set('port', v)} />
          </Field>
          <Field label="خيارات">
            <div className="flex gap-1.5">
              <Check on={inputs.with_eur1} onChange={v => set('with_eur1', v)} label="EUR 1" />
              <Check on={inputs.collect_from_showroom} onChange={v => set('collect_from_showroom', v)} label="استلام من المعرض" />
            </div>
          </Field>
          <Field label="سعر الصرف (ج.م/€)">
            <input inputMode="decimal" dir="ltr" placeholder="—" value={inputs.fx_rate_egp} onChange={e => set('fx_rate_egp', e.target.value)} className={NUM} title={fx_note} />
          </Field>
          {more && (
            <>
              <Field label="خصم المصاريف (€) — بموافقة الإدارة">
                <input inputMode="decimal" dir="ltr" placeholder="0" value={inputs.admin_fee_discount_eur} onChange={e => set('admin_fee_discount_eur', e.target.value)} className={NUM} />
              </Field>
              <Field label="الضريبة %">
                <input inputMode="decimal" dir="ltr" value={inputs.vat_rate_pct} onChange={e => set('vat_rate_pct', e.target.value)} className={NUM} />
              </Field>
            </>
          )}
          <button type="button" onClick={() => setMore(m => !m)} className="h-8 self-end text-[12px] text-slate-500 hover:text-slate-800 underline underline-offset-2">
            {more ? 'أقل' : 'خصم / ضريبة'}
          </button>
          <div className="ms-auto flex gap-1.5 self-end">
            <Button variant="outline-secondary" size="sm" disabled={!has} onClick={copy}><Lucide icon="Copy" className="w-3.5 h-3.5 ms-1" />انسخ</Button>
            {can_save && <Button variant="primary" size="sm" disabled={!has || saving} onClick={save}><Lucide icon="Save" className="w-3.5 h-3.5 ms-1" />{saving ? 'بيتحفظ…' : 'احفظ كعرض سعر'}</Button>}
          </div>
        </div>

        {error && <div className="px-3 py-1.5 text-[12.5px] text-red-700 bg-red-50 border-b border-red-100">{error}</div>}

        {/* ── ledgers ─────────────────────────────────────────────── */}
        {!has ? (
          <div className="px-3 py-6 text-center text-slate-400">اكتب سعر الإعلان — الأرقام بتتحسب على السيرفر بنفس محرك عرض السعر</div>
        ) : (
          <div className="grid md:grid-cols-[3fr_2fr]">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-emerald-50 text-emerald-800">
                  <th className="py-1.5 px-2 text-start font-semibold">باليورو</th>
                  <th className="py-1.5 px-2 text-end font-normal text-[12px]">{result!.band_label}</th>
                </tr>
              </thead>
              <tbody>
                <Ln tone="eur" k="سعر الإعلان (شامل الضريبة)" v={Number(inputs.gross_price_eur)} />
                <Ln tone="eur" k="الضريبة الألمانية المستردة" v={result!.vat_reclaimable_eur} neg={Number(result!.vat_reclaimable_eur) > 0} />
                <Ln tone="eur" k="صافي سعر العربية" v={result!.net_eur} />
                <Ln tone="eur" k="الشحن" v={result!.shipping_eur} />
                <Ln tone="eur" k="المصاريف الإدارية (حسب الفئة)" v={result!.admin_fee_before_discount_eur} />
                {discount > 0.005 && <Ln tone="eur" k="خصم على المصاريف" v={discount} neg />}
                {Number(result!.eur1_eur) > 0 && <Ln tone="eur" k="شهادة EUR 1" v={result!.eur1_eur} />}
                {Number(result!.shipping_extra_eur) > 0 && <Ln tone="eur" k="إضافة الشحن" v={result!.shipping_extra_eur} />}
                <Ln tone="eur" k="= إجمالي السعر" v={result!.total_eur} sum />
                <Ln tone="eur" k={<>الوديعة <span className="text-slate-400">{Number(result!.deposit_pct) ? `${Number(result!.deposit_pct)}%` : ''}</span></>} v={result!.deposit_eur} />
                <Ln tone="eur" k="الباقي قبل الشحن" v={result!.balance_eur} />
              </tbody>
            </table>
            <table className="w-full border-collapse border-s border-slate-200 self-start">
              <thead>
                <tr className="bg-orange-50 text-orange-800">
                  <th className="py-1.5 px-2 text-start font-semibold">بالجنيه — عند الوصول</th>
                  <th className="py-1.5 px-2 text-end font-normal text-[11px]">ما بيتجمعش مع اليورو</th>
                </tr>
              </thead>
              <tbody>
                <Ln tone="egp" k="الميناء والتخليص" v={result!.port_fee_egp} />
                {Number(result!.showroom_fee_egp) > 0 && <Ln tone="egp" k="استلام من المعرض" v={result!.showroom_fee_egp} />}
                <Ln tone="egp" k="= المستحق عند الوصول" v={result!.egp_due_on_arrival} sum />
                {result!.total_egp_indicative && Number(result!.total_egp_indicative) > 0 && (
                  <tr className="border-t border-dashed border-slate-300 text-slate-500">
                    <td className="py-1 px-2 text-[12px]">الإجمالي بالجنيه، تقريبي بسعر اليوم</td>
                    <td dir="ltr" className="py-1 px-2 text-right font-mono tabular-nums">{money(result!.total_egp_indicative)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
