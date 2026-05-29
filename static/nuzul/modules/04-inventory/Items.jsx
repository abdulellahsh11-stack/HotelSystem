/* @jsx React.createElement */
/* global React, NzIcon */

const { useState: useStateInv } = React;

function CategoryRail({ active, onChange }) {
  const groups = [
    { label: "المخزون · Linens & amenities", cats: [
      { id: "linens",    ar: "لُحف وأغطية",      ic: "🛏", count: 1240 },
      { id: "sheets",    ar: "مفارش",            ic: "📜", count: 980  },
      { id: "pillows",   ar: "مخدات",            ic: "🪶", count: 642  },
      { id: "pillowcs",  ar: "أغطية مخدات",      ic: "🧺", count: 1820 },
      { id: "personal",  ar: "عناية شخصية",     ic: "🧴", count: 4200 },
      { id: "soap",      ar: "صابون ونظافة",    ic: "🧼", count: 3600 },
      { id: "perfumes",  ar: "عطور",             ic: "✨", count:  280 },
    ]},
    { label: "المستودع · MEP & maintenance", cats: [
      { id: "screens",   ar: "شاشات",            ic: "📺", count: 48  },
      { id: "wires",     ar: "أسلاك",            ic: "🔌", count: 230 },
      { id: "paint",     ar: "أصباغ",            ic: "🎨", count: 86  },
      { id: "ladders",   ar: "سلالم وسقالات",   ic: "🪜", count: 12  },
      { id: "lights",    ar: "إنارة",            ic: "💡", count: 540 },
      { id: "switches",  ar: "مفاتيح",           ic: "⚙️", count: 320 },
    ]},
  ];
  return (
    <aside className="inv-rail">
      {groups.map(g => (
        <div className="inv-grp" key={g.label}>
          <div className="inv-grp-lbl">{g.label}</div>
          {g.cats.map(c => (
            <a key={c.id} onClick={() => onChange(c.id)} className={"inv-cat " + (active === c.id ? "is-on" : "")}>
              <span className="ic">{c.ic}</span>
              <span className="nm">{c.ar}</span>
              <span className="ct">{c.count}</span>
            </a>
          ))}
        </div>
      ))}
      <a className="inv-cat is-add"><NzIcon.plus/><span>تخصيص فئة جديدة</span></a>
    </aside>
  );
}

function StockBar({ value, par, reorder }) {
  const pct = Math.min(100, (value / par) * 100);
  const status = value <= reorder ? "low" : value < par * 0.5 ? "warn" : "ok";
  return (
    <div className="inv-stock">
      <div className="bar">
        <div className={"fill " + status} style={{width: pct + "%"}}></div>
        <div className="par-mark" style={{insetInlineStart: ((reorder/par)*100) + "%"}}>
          <span className="par-tick"></span>
          <span className="par-lab">إعادة طلب</span>
        </div>
      </div>
      <div className="num">
        <span className="v">{value.toLocaleString("ar-EG")}</span>
        <span className="sep">/</span>
        <span className="p">{par.toLocaleString("ar-EG")}</span>
      </div>
    </div>
  );
}

function ItemsTable({ items }) {
  return (
    <div className="inv-tbl">
      <div className="inv-tr inv-th">
        <span>المنتج</span>
        <span>الموقع</span>
        <span>المستوى</span>
        <span>آخر حركة</span>
        <span>الحالة</span>
        <span></span>
      </div>
      {items.map(it => {
        const status = it.qty <= it.reorder ? { cls: "err",  ar: "تحت الحد" }
                     : it.qty < it.par*0.5  ? { cls: "warn", ar: "منخفض"   }
                     : { cls: "ok", ar: "متوفر" };
        return (
          <div className="inv-tr" key={it.sku}>
            <div className="inv-name">
              <span className="ico">{it.ic}</span>
              <div>
                <div className="ar">{it.name}</div>
                <div className="sku">SKU · {it.sku}</div>
              </div>
            </div>
            <div className="loc">
              <div>{it.loc}</div>
              <div className="sub">{it.zone}</div>
            </div>
            <StockBar value={it.qty} par={it.par} reorder={it.reorder}/>
            <div className="mv">
              <div className={"d " + (it.dir === "in" ? "in" : "out")}>{it.dir === "in" ? "+" : "−"}{it.move}</div>
              <div className="sub">{it.when}</div>
            </div>
            <span className={"nz-pill " + status.cls}><span className="d"></span>{status.ar}</span>
            <button className="nz-icon-btn" style={{background: "transparent", border: "none", color: "var(--fg-3)"}}><NzIcon.dots/></button>
          </div>
        );
      })}
    </div>
  );
}

window.CategoryRail = CategoryRail;
window.ItemsTable = ItemsTable;
window.StockBar = StockBar;
