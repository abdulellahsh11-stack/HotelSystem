/* @jsx React.createElement */
/* global React, Icon */

function KpiCard({ label, labelEn, value, suffix, delta, deltaLabel, accent }) {
  const up = (delta || "").startsWith("+");
  return (
    <div className={"dh-kpi " + (accent ? "is-accent" : "")}>
      <div className="dh-kpi-head">
        <span className="lbl">{label}</span>
        <span className="lbl-en">{labelEn}</span>
      </div>
      <div className="dh-kpi-value">
        <span className="v">{value}</span>
        {suffix ? <span className="sx">{suffix}</span> : null}
      </div>
      {delta ? (
        <div className={"dh-kpi-delta " + (up ? "is-up" : "is-down")}>
          <span className="ar">
            {up ? <Icon.arrow_up/> : <Icon.arrow_dn/>}
            <span>{delta}</span>
          </span>
          <span className="lab">{deltaLabel}</span>
        </div>
      ) : null}
    </div>
  );
}

function KpiGrid() {
  return (
    <div className="dh-kpi-grid" data-m-rise-stagger>
      <KpiCard label="إشغال الليلة"  labelEn="Occupancy"     value="٨٧" suffix="٪" delta="+٤٪" deltaLabel="عن أمس" accent />
      <KpiCard label="ADR · متوسط السعر" labelEn="Avg. daily rate" value="٧٢٠" suffix="ر.س" delta="+١٢٪" deltaLabel="هذا الموسم" />
      <KpiCard label="RevPAR"        labelEn="Rev. per room"  value="٦٢٦" suffix="ر.س" delta="+٧٪"  deltaLabel="عن الأسبوع" />
      <KpiCard label="إيراد اليوم"   labelEn="Today's revenue" value="٢٤٬٨٦٠" suffix="ر.س" delta="+١٨٪" deltaLabel="مقابل المتوقع" />
      <KpiCard label="حجوزات قادمة" labelEn="Upcoming · 7d"  value="١٤٢" delta="-٣"  deltaLabel="عن الأسبوع" />
      <KpiCard label="تذاكر صيانة"  labelEn="Maintenance"     value="٧"  delta="+٢"  deltaLabel="مفتوحة الآن" />
    </div>
  );
}

window.KpiCard = KpiCard;
window.KpiGrid = KpiGrid;
