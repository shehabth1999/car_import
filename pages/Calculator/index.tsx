import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Head, usePage } from '@inertiajs/react';
import Button from '@/components/Base/Button';
import Lucide from '@/components/Base/Lucide';
import toast from '@/utils/toast';

declare const window: Window & { axios: any };

/**
 * The calculator — the client's spreadsheet as a page.
 *
 * Nothing here computes a price. Every keystroke posts the inputs to
 * /car-import/calculator/compute/, which runs `Quote._live_values()` — the same
 * engine, the same bands, the same rounding the quotation form uses. The page
 * only draws the answer: two ledgers, euros and pounds, that never add up.
 */

type Choice = [string, string];

interface Props {
  shipping_types: Choice[];
  ports: Choice[];
  fx_rate: number | '';
  fx_note: string;
  can_save: boolean;
}

interface Result {
  band_label: string;
  net_eur: number;
  vat_reclaimable_eur: number;
  shipping_eur: number;
  admin_fee_before_discount_eur: number;
  admin_fee_eur: number;
  eur1_eur: number;
  shipping_extra_eur: number;
  total_eur: number;
  deposit_pct: number;
  deposit_eur: number;
  balance_eur: number;
  port_fee_egp: number;
  showroom_fee_egp: number;
  egp_due_on_arrival: number;
  total_egp_indicative: number | null;
  pricing_error: string;
}

interface Inputs {
  gross_price_eur: string;
  vat_rate_pct: string;
  with_eur1: boolean;
  shipping_type: '' | 'vip_roro' | 'container';
  port: 'alexandria' | 'port_said';
  collect_from_showroom: boolean;
  admin_fee_discount_eur: string;
  fx_rate_egp: string;
}

const T = {
  canvas: '#EDF1F4', ink: '#14213D', muted: '#5B6B7F', line: '#D5DCE3',
  euro: '#1F6F5F', euroTint: '#E6F2EE', pound: '#B8621B', poundTint: '#FBEFE4', danger: '#C8102E',
};

const fmt = new Intl.NumberFormat('en-EG', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money = (n: number | null | undefined) => (n === null || n === undefined ? '—' : fmt.format(Math.abs(Number(n))));

const SHIPPING_LABEL: Record<string, string> = { standard: 'عادي', vip_roro: 'VIP RORO', container: 'كونتينر' };
const PORT_LABEL: Record<string, string> = { alexandria: 'الإسكندرية', port_said: 'بورسعيد' };

/* ── small pieces ─────────────────────────────────────────────────────── */

function Segmented<V extends string>({ options, value, onChange, label }:
  { options: Choice[]; value: V; onChange: (v: V) => void; label: string }) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-lg overflow-hidden border" style={{ borderColor: T.line }}>
      {options.map(([key, text]) => {
        const on = key === value;
        return (
          <button key={key} type="button" aria-pressed={on} onClick={() => onChange(key as V)}
            className="px-3 py-1.5 text-[13.5px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
            style={{ background: on ? T.ink : '#FBFCFD', color: on ? '#fff' : T.ink, borderInlineStart: `1px solid ${T.line}` }}>
            {text}
          </button>
        );
      })}
    </div>
  );
}

function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)}
      className="relative h-6 w-[42px] rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
      style={{ background: on ? T.euro : T.line }}>
      <span className="absolute top-[3px] h-[18px] w-[18px] rounded-full bg-white transition-transform"
        style={{ insetInlineStart: 3, transform: on ? 'translateX(-18px)' : 'none' }} />
    </button>
  );
}

function Row({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5" style={{ borderTop: `1px solid ${T.line}` }}>
      <div className="font-medium">{label}{hint && <small className="block font-normal text-[12px]" style={{ color: T.muted }}>{hint}</small>}</div>
      {children}
    </div>
  );
}

function Line({ label, hint, value, negative, sum, big }:
  { label: string; hint?: string; value: React.ReactNode; negative?: boolean; sum?: boolean; big?: boolean }) {
  const ref = useRef<HTMLSpanElement>(null);
  const prev = useRef<React.ReactNode>(null);
  useEffect(() => {
    if (prev.current !== null && prev.current !== value && ref.current && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      ref.current.animate([{ background: '#FFF4CC' }, { background: 'transparent' }], { duration: 350 });
    }
    prev.current = value;
  }, [value]);
  return (
    <div className={`flex items-baseline justify-between px-3.5 py-2 ${sum ? 'font-bold' : ''}`} style={{ borderTop: `1px solid ${T.line}` }}>
      <span>{label}{hint && <small className="ms-1.5 text-[12px]" style={{ color: T.muted }}>{hint}</small>}</span>
      <span ref={ref} dir="ltr" className={`font-mono tabular-nums rounded px-1 ${big ? 'text-[26px] font-semibold' : sum ? 'text-[20px] font-semibold' : 'font-medium'}`}
        style={{ color: negative ? T.muted : undefined }}>
        {negative ? '− ' : ''}{value}
      </span>
    </div>
  );
}

/* ── the page ─────────────────────────────────────────────────────────── */

export default function Calculator() {
  const { props } = usePage();
  const { shipping_types, ports, fx_rate, fx_note, can_save } = props as unknown as Props;

  const [inputs, setInputs] = useState<Inputs>({
    gross_price_eur: '', vat_rate_pct: '19', with_eur1: false, shipping_type: '', port: 'alexandria',
    collect_from_showroom: false, admin_fee_discount_eur: '', fx_rate_egp: fx_rate === '' ? '' : String(fx_rate),
  });
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const inflight = useRef(0);
  const set = <K extends keyof Inputs>(key: K, value: Inputs[K]) => setInputs(s => ({ ...s, [key]: value }));

  // Every change → the server. Debounced so a typed "48001" is one request, not five.
  useEffect(() => {
    if (!inputs.gross_price_eur) { setResult(null); setError(''); return; }
    const mine = ++inflight.current;
    const timer = setTimeout(async () => {
      try {
        const r = await window.axios.post('/car-import/calculator/compute/', {
          ...inputs, admin_fee_discount_eur: inputs.admin_fee_discount_eur || 0,
        });
        if (mine !== inflight.current) return;
        const v: Result = r.data?.value;
        setResult(v); setError(v?.pricing_error || '');
      } catch (e: any) {
        if (mine !== inflight.current) return;
        setResult(null); setError(e?.response?.data?.error || 'الحساب ما رجعش من السيرفر');
      }
    }, 220);
    return () => clearTimeout(timer);
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
    } catch (e: any) {
      setError(e?.response?.data?.error || 'ما اتحفظش');
      setSaving(false);
    }
  }, [inputs]);

  return (
    <div dir="rtl" className="font-arabic min-h-full" style={{ background: T.canvas, color: T.ink }}>
      <Head title="الآلة الحاسبة" />
      <div className="mx-auto max-w-[1120px] px-4 pt-5 pb-10">
        <header className="flex flex-wrap items-baseline justify-between gap-3 mb-3">
          <div>
            <h1 className="text-[20px] font-bold m-0">الآلة الحاسبة</h1>
            <div className="text-[13px]" style={{ color: T.muted }}>نفس محرك عرض السعر — الفئات والمصاريف المعتمدة، محدش بيقدر يكتب عليها</div>
          </div>
        </header>

        <div className="grid gap-4 md:grid-cols-[5fr_7fr]">
          {/* ── inputs ─────────────────────────────────────────── */}
          <section className="rounded-[10px] border bg-white p-[18px]" style={{ borderColor: T.line }} aria-labelledby="in-h">
            <h2 id="in-h" className="text-[13px] font-semibold m-0 mb-3" style={{ color: T.muted }}>اللي بتكتبه</h2>

            <label htmlFor="price" className="block font-semibold mb-1.5">سعر الإعلان في ألمانيا، شامل الضريبة</label>
            <div className="flex items-center rounded-[10px] border-[1.5px] px-3 py-1 bg-[#FBFCFD] focus-within:ring-[3px]"
              style={{ borderColor: T.line, ['--tw-ring-color' as any]: 'rgba(20,33,61,.12)' }}>
              <input id="price" inputMode="decimal" autoFocus autoComplete="off" placeholder="48001" dir="ltr"
                value={inputs.gross_price_eur}
                onChange={e => set('gross_price_eur', e.target.value.replace(/[^\d.]/g, ''))}
                className="flex-1 min-w-0 border-0 bg-transparent outline-none font-mono text-[30px] font-semibold leading-tight text-left focus:ring-0" />
              <span className="font-semibold text-[16px]" style={{ color: T.euro }}>€</span>
            </div>
            <div className="text-[12.5px] mt-1.5" style={{ color: error ? T.danger : T.muted }}>
              {error || 'الرقم اللي على الإعلان. كل حاجة تحت بتتحسب منه.'}
            </div>

            <div className="mt-3.5">
              <Row label="شهادة EUR 1" hint="إثبات منشأ أوروبي — جمارك أقل">
                <Toggle on={inputs.with_eur1} onChange={v => set('with_eur1', v)} label="شهادة EUR 1" />
              </Row>
              <Row label="الشحن">
                <Segmented label="نوع الشحن" value={(inputs.shipping_type || 'standard') as any}
                  options={shipping_types.map(([k]) => [k, SHIPPING_LABEL[k] || k])}
                  onChange={v => set('shipping_type', (v === 'standard' ? '' : v) as Inputs['shipping_type'])} />
              </Row>
              <Row label="ميناء الوصول">
                <Segmented label="الميناء" value={inputs.port} options={ports.map(([k]) => [k, PORT_LABEL[k] || k])} onChange={v => set('port', v)} />
              </Row>
              <Row label="استلام من المعرض" hint="بدل التوصيل لحد الباب">
                <Toggle on={inputs.collect_from_showroom} onChange={v => set('collect_from_showroom', v)} label="استلام من المعرض" />
              </Row>
              <Row label="سعر الصرف" hint={fx_note}>
                <input inputMode="decimal" dir="ltr" aria-label="جنيه لكل يورو" placeholder="—" value={inputs.fx_rate_egp}
                  onChange={e => set('fx_rate_egp', e.target.value)}
                  className="w-[120px] rounded-lg border px-2.5 py-1.5 font-mono text-[15px] text-left bg-[#FBFCFD]" style={{ borderColor: T.line }} />
              </Row>
              <details className="mt-2 group">
                <summary className="cursor-pointer text-[13px] list-none" style={{ color: T.muted }}>
                  <span className="group-open:hidden">＋ </span><span className="hidden group-open:inline">－ </span>خصم على المصاريف الإدارية أو ضريبة مختلفة
                </summary>
                <Row label="خصم على المصاريف" hint="أي خصم محتاج موافقة الإدارة عند الحفظ">
                  <input inputMode="decimal" dir="ltr" aria-label="الخصم باليورو" placeholder="0" value={inputs.admin_fee_discount_eur}
                    onChange={e => set('admin_fee_discount_eur', e.target.value)}
                    className="w-[120px] rounded-lg border px-2.5 py-1.5 font-mono text-[15px] text-left bg-[#FBFCFD]" style={{ borderColor: T.line }} />
                </Row>
                <Row label="الضريبة الألمانية %">
                  <input inputMode="decimal" dir="ltr" aria-label="نسبة الضريبة" value={inputs.vat_rate_pct}
                    onChange={e => set('vat_rate_pct', e.target.value)}
                    className="w-[120px] rounded-lg border px-2.5 py-1.5 font-mono text-[15px] text-left bg-[#FBFCFD]" style={{ borderColor: T.line }} />
                </Row>
              </details>
            </div>

            <div className="flex flex-wrap gap-2.5 mt-4">
              {can_save && (
                <Button variant="primary" disabled={!has || saving} onClick={save}>
                  <Lucide icon="Save" className="w-4 h-4 ms-1" />{saving ? 'بيتحفظ…' : 'احفظ كعرض سعر'}
                </Button>
              )}
              <Button variant="outline-secondary" disabled={!has} onClick={copy}>
                <Lucide icon="Copy" className="w-4 h-4 ms-1" />انسخ الأرقام
              </Button>
            </div>
            <p className="text-[12.5px] mt-3 mb-0" style={{ color: T.muted }}>
              الأرقام بتتحسب على السيرفر بنفس محرك عرض السعر. اللي هنا مش محفوظ لحد ما تدوس «احفظ كعرض سعر» — وقتها بيتجمّد بتاريخ واسمك.
            </p>
          </section>

          {/* ── the stack ───────────────────────────────────────── */}
          <section className="rounded-[10px] border bg-white p-[18px]" style={{ borderColor: T.line }} aria-labelledby="out-h" aria-live="polite">
            <h2 id="out-h" className="text-[13px] font-semibold m-0 mb-3" style={{ color: T.muted }}>السعر كما يراه العميل</h2>

            <div className="rounded-[10px] border overflow-hidden" style={{ borderColor: T.line }}>
              <div className="flex items-center justify-between px-3.5 py-2.5 text-[13px] font-semibold" style={{ background: T.euroTint, color: T.euro }}>
                <span>باليورو</span>
                <span className="rounded-full border bg-white px-2 text-[12px] font-medium" style={{ borderColor: 'currentColor' }}>{result?.band_label || '—'}</span>
              </div>
              {!has ? (
                <div className="py-6 text-center" style={{ color: T.muted, borderTop: `1px solid ${T.line}` }}>اكتب السعر عشان الستاك يظهر</div>
              ) : (
                <>
                  <Line label="سعر الإعلان" hint="شامل الضريبة" value={money(Number(inputs.gross_price_eur))} />
                  <Line label="الضريبة الألمانية المستردة" value={money(result!.vat_reclaimable_eur)} negative={Number(result!.vat_reclaimable_eur) > 0} />
                  <Line label="صافي سعر العربية" value={money(result!.net_eur)} />
                  <Line label="الشحن" value={money(result!.shipping_eur)} />
                  <Line label="المصاريف الإدارية" hint="حسب الفئة" value={money(result!.admin_fee_before_discount_eur)} />
                  {discount > 0.005 && <Line label="خصم على المصاريف" value={money(discount)} negative />}
                  {Number(result!.eur1_eur) > 0 && <Line label="شهادة EUR 1" value={money(result!.eur1_eur)} />}
                  {Number(result!.shipping_extra_eur) > 0 && <Line label="إضافة الشحن" value={money(result!.shipping_extra_eur)} />}
                  <div style={{ background: T.euroTint }}>
                    <Line label="= إجمالي السعر" value={money(result!.total_eur)} sum big />
                  </div>
                  <div className="grid grid-cols-2">
                    <div className="px-3.5 py-2" style={{ borderTop: `1px solid ${T.line}` }}>
                      <div className="text-[13px]">الوديعة <small style={{ color: T.muted }}>{Number(result!.deposit_pct) ? `${Number(result!.deposit_pct)}%` : ''}</small></div>
                      <div dir="ltr" className="font-mono tabular-nums text-[18px] font-semibold text-right" style={{ direction: 'ltr' }}>{money(result!.deposit_eur)}</div>
                    </div>
                    <div className="px-3.5 py-2" style={{ borderTop: `1px solid ${T.line}`, borderInlineStart: `1px solid ${T.line}` }}>
                      <div className="text-[13px]">الباقي <small style={{ color: T.muted }}>قبل الشحن</small></div>
                      <div dir="ltr" className="font-mono tabular-nums text-[18px] font-semibold text-right">{money(result!.balance_eur)}</div>
                    </div>
                  </div>
                </>
              )}
            </div>

            {has && result!.total_egp_indicative && Number(result!.total_egp_indicative) > 0 && (
              <div className="flex items-center gap-2.5 my-3 mx-1 text-[12.5px]" style={{ color: T.muted }}>
                <span>تقريبي بسعر اليوم</span>
                <span className="flex-1" style={{ borderTop: `2px dotted ${T.line}` }} />
                <span dir="ltr" className="font-mono font-medium" style={{ color: T.ink }}>{money(result!.total_egp_indicative)}</span>
                <span>ج.م</span>
              </div>
            )}

            {has && (
              <div className="rounded-[10px] border overflow-hidden mt-3.5" style={{ borderColor: T.line }}>
                <div className="flex items-center justify-between px-3.5 py-2.5 text-[13px] font-semibold" style={{ background: T.poundTint, color: T.pound }}>
                  <span>بالجنيه — بيتدفع في مصر عند الوصول</span>
                  <span className="rounded-full border bg-white px-2 text-[12px] font-medium" style={{ borderColor: 'currentColor' }}>ما بيتجمعش مع اليورو</span>
                </div>
                <Line label="مصاريف الميناء والتخليص" value={money(result!.port_fee_egp)} />
                {Number(result!.showroom_fee_egp) > 0 && <Line label="استلام من المعرض" value={money(result!.showroom_fee_egp)} />}
                <div style={{ background: T.poundTint }}>
                  <Line label="= المستحق عند الوصول" value={money(result!.egp_due_on_arrival)} sum />
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
