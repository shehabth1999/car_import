import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Head, usePage } from '@inertiajs/react';
import Button from '@/components/Base/Button';
import Lucide from '@/components/Base/Lucide';
import { FormInput, FormLabel, FormSelect, FormSwitch } from '@/components/Base/Form';
import toast from '@/utils/toast';

declare const window: Window & { axios: any };

/**
 * The calculator — the client's spreadsheet as a screen.
 *
 * Two cards: what the salesman types, and what the customer is told. Every
 * change posts to /car-import/calculator/compute/, which runs
 * `Quote._live_values()` — the quotation form's own engine. Nothing here
 * computes a price. Styled with the app's semantic tokens (surface / content /
 * edge / primary / warning) so it themes light and dark by construction.
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
const SHIPPING_LABEL: Record<string, string> = { standard: 'عادي (RORO)', vip_roro: 'VIP RORO', container: 'كونتينر' };
const PORT_LABEL: Record<string, string> = { alexandria: 'الإسكندرية', port_said: 'بورسعيد' };

/* ── pieces ───────────────────────────────────────────────────────────── */

function Card({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-edge bg-surface shadow-sm">
      <header className="flex items-center justify-between gap-2 border-b border-edge px-4 py-2.5">
        <h2 className="m-0 text-sm font-semibold text-content">{title}</h2>
        {aside}
      </header>
      {children}
    </section>
  );
}

function Row({ k, v, neg, muted, sum, tone = 'primary' }:
  { k: React.ReactNode; v: number | null | undefined; neg?: boolean; muted?: boolean; sum?: boolean; tone?: 'primary' | 'warning' }) {
  const sumCls = tone === 'primary' ? 'bg-primary/10 text-primary' : 'bg-warning/10 text-warning';
  return (
    <div className={`flex items-baseline justify-between gap-3 px-4 py-1.5 border-t border-edge ${sum ? `${sumCls} font-bold` : ''} ${muted ? 'text-content-subtle' : ''}`}>
      <span className={`text-sm ${sum ? '' : 'text-content-muted'}`}>{k}</span>
      <span dir="ltr" className={`font-mono tabular-nums ${sum ? 'text-base' : 'text-sm'} ${neg ? 'text-content-subtle' : sum ? '' : 'text-content'}`}>
        {neg ? '− ' : ''}{money(v)}
      </span>
    </div>
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
    return <div dir="rtl" className="p-5 text-sm text-content-muted">الآلة الحاسبة لفريق المبيعات. اطلب من مدير المبيعات يضيفك للمجموعة.</div>;
  }

  return (
    <div dir="rtl" className="p-4 lg:p-5">
      <Head title="الآلة الحاسبة" />

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="m-0 text-lg font-semibold text-content">الآلة الحاسبة</h1>
          <p className="m-0 text-xs text-content-muted">نفس محرك عرض السعر — الفئات والمصاريف المعتمدة، والأرقام بتتحسب على السيرفر وإنت بتكتب.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline-secondary" size="sm" disabled={!has} onClick={copy}>
            <Lucide icon="Copy" className="ms-1 h-4 w-4" /> انسخ الأرقام
          </Button>
          {can_save && (
            <Button variant="primary" size="sm" disabled={!has || saving} onClick={save}>
              <Lucide icon="Save" className="ms-1 h-4 w-4" /> {saving ? 'بيتحفظ…' : 'احفظ كعرض سعر'}
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* ── inputs ─────────────────────────────────────────── */}
        <Card title="اللي بتكتبه">
          <div className="space-y-4 p-4">
            <div>
              <FormLabel htmlFor="price">سعر الإعلان في ألمانيا، شامل الضريبة (€)</FormLabel>
              <FormInput id="price" inputMode="decimal" autoFocus autoComplete="off" placeholder="48001" dir="ltr"
                value={inputs.gross_price_eur} onChange={e => set('gross_price_eur', e.target.value.replace(/[^\d.]/g, ''))}
                className="font-mono text-lg font-semibold" />
              <p className={`mt-1 text-xs ${error ? 'text-danger' : 'text-content-subtle'}`}>
                {error || 'الرقم اللي على الإعلان. كل حاجة تحت بتتحسب منه.'}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <FormLabel htmlFor="shipping">الشحن</FormLabel>
                <FormSelect id="shipping" value={inputs.shipping_type || 'standard'}
                  onChange={e => set('shipping_type', (e.target.value === 'standard' ? '' : e.target.value) as Inputs['shipping_type'])}>
                  {shipping_types.map(([k]) => <option key={k} value={k}>{SHIPPING_LABEL[k] || k}</option>)}
                </FormSelect>
              </div>
              <div>
                <FormLabel htmlFor="port">ميناء الوصول</FormLabel>
                <FormSelect id="port" value={inputs.port} onChange={e => set('port', e.target.value as Inputs['port'])}>
                  {ports.map(([k]) => <option key={k} value={k}>{PORT_LABEL[k] || k}</option>)}
                </FormSelect>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <FormSwitch className="flex items-center gap-2">
                <FormSwitch.Input id="eur1" type="checkbox" checked={inputs.with_eur1} onChange={e => set('with_eur1', e.target.checked)} />
                <FormSwitch.Label htmlFor="eur1" className="text-sm">
                  شهادة EUR 1 <span className="block text-xs text-content-subtle">إثبات منشأ أوروبي — جمارك أقل</span>
                </FormSwitch.Label>
              </FormSwitch>
              <FormSwitch className="flex items-center gap-2">
                <FormSwitch.Input id="showroom" type="checkbox" checked={inputs.collect_from_showroom} onChange={e => set('collect_from_showroom', e.target.checked)} />
                <FormSwitch.Label htmlFor="showroom" className="text-sm">
                  استلام من المعرض <span className="block text-xs text-content-subtle">بدل التوصيل لحد الباب</span>
                </FormSwitch.Label>
              </FormSwitch>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <FormLabel htmlFor="fx">سعر الصرف (ج.م لكل €)</FormLabel>
                <FormInput id="fx" inputMode="decimal" dir="ltr" placeholder="—" value={inputs.fx_rate_egp} onChange={e => set('fx_rate_egp', e.target.value)} className="font-mono" />
                <p className="mt-1 text-xs text-content-subtle">{fx_note}</p>
              </div>
              <div className="flex items-end">
                <button type="button" onClick={() => setMore(m => !m)} className="mb-1 text-xs text-content-muted underline underline-offset-2 hover:text-content">
                  {more ? 'إخفاء الخصم والضريبة' : 'خصم على المصاريف / ضريبة مختلفة'}
                </button>
              </div>
            </div>

            {more && (
              <div className="grid grid-cols-2 gap-3 rounded-md border border-edge bg-surface-sunken p-3">
                <div>
                  <FormLabel htmlFor="discount">خصم على المصاريف الإدارية (€)</FormLabel>
                  <FormInput id="discount" inputMode="decimal" dir="ltr" placeholder="0" value={inputs.admin_fee_discount_eur} onChange={e => set('admin_fee_discount_eur', e.target.value)} className="font-mono" />
                  <p className="mt-1 text-xs text-content-subtle">أي خصم محتاج موافقة الإدارة عند الحفظ</p>
                </div>
                <div>
                  <FormLabel htmlFor="vat">الضريبة الألمانية %</FormLabel>
                  <FormInput id="vat" inputMode="decimal" dir="ltr" value={inputs.vat_rate_pct} onChange={e => set('vat_rate_pct', e.target.value)} className="font-mono" />
                </div>
              </div>
            )}
          </div>
        </Card>

        {/* ── the stack ───────────────────────────────────────── */}
        <Card title="السعر كما يراه العميل"
          aside={has ? <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">{result!.band_label}</span> : null}>
          {!has ? (
            <div className="px-4 py-10 text-center text-sm text-content-subtle">اكتب سعر الإعلان عشان الأرقام تظهر</div>
          ) : (
            <div className="pb-2">
              <div className="px-4 pt-3 pb-1 text-xs font-semibold text-primary">باليورو</div>
              <Row k="سعر الإعلان (شامل الضريبة)" v={Number(inputs.gross_price_eur)} />
              <Row k="الضريبة الألمانية المستردة" v={result!.vat_reclaimable_eur} neg={Number(result!.vat_reclaimable_eur) > 0} />
              <Row k="صافي سعر العربية" v={result!.net_eur} />
              <Row k="الشحن" v={result!.shipping_eur} />
              <Row k="المصاريف الإدارية (حسب الفئة)" v={result!.admin_fee_before_discount_eur} />
              {discount > 0.005 && <Row k="خصم على المصاريف" v={discount} neg />}
              {Number(result!.eur1_eur) > 0 && <Row k="شهادة EUR 1" v={result!.eur1_eur} />}
              {Number(result!.shipping_extra_eur) > 0 && <Row k="إضافة الشحن" v={result!.shipping_extra_eur} />}
              <Row k="إجمالي السعر" v={result!.total_eur} sum />
              <div className="grid grid-cols-2 border-t border-edge">
                <div className="px-4 py-2">
                  <div className="text-xs text-content-muted">الوديعة {Number(result!.deposit_pct) ? <span className="text-content-subtle">({Number(result!.deposit_pct)}%)</span> : null}</div>
                  <div dir="ltr" className="text-right font-mono text-base font-semibold text-content tabular-nums">{money(result!.deposit_eur)}</div>
                </div>
                <div className="border-s border-edge px-4 py-2">
                  <div className="text-xs text-content-muted">الباقي قبل الشحن</div>
                  <div dir="ltr" className="text-right font-mono text-base font-semibold text-content tabular-nums">{money(result!.balance_eur)}</div>
                </div>
              </div>

              <div className="mt-2 flex items-center justify-between px-4 pt-3 pb-1 text-xs font-semibold text-warning">
                <span>بالجنيه — بيتدفع في مصر عند الوصول</span>
                <span className="font-normal text-content-subtle">ما بيتجمعش مع اليورو</span>
              </div>
              <Row tone="warning" k="مصاريف الميناء والتخليص" v={result!.port_fee_egp} />
              {Number(result!.showroom_fee_egp) > 0 && <Row tone="warning" k="استلام من المعرض" v={result!.showroom_fee_egp} />}
              <Row tone="warning" k="المستحق عند الوصول" v={result!.egp_due_on_arrival} sum />
              {result!.total_egp_indicative && Number(result!.total_egp_indicative) > 0 && (
                <Row k="الإجمالي بالجنيه — تقريبي بسعر اليوم، مش وعد" v={result!.total_egp_indicative} muted />
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
