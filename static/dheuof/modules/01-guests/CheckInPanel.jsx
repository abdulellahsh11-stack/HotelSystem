/* @jsx React.createElement */
/* global React, NzIcon */

const { useState: useState_ck } = React;

function CheckInPanel() {
  const [step, setStep] = useState_ck(1);

  return (
    <div className="fd-panel">
      <div className="dh-card-head">
        <div>
          <div className="ttl">تسجيل دخول سريع</div>
          <div className="sub">Quick check-in · 3 steps</div>
        </div>
        <div className="fd-steps">
          {[1,2,3].map(n => (
            <span key={n} className={"fd-step " + (n === step ? "is-on" : n < step ? "is-done" : "")}>{n}</span>
          ))}
        </div>
      </div>

      <div className="fd-body">
        {step === 1 ? (
          <div className="fd-id">
            <div className="fd-scan">
              <div className="ring"></div>
              <NzIcon.scan/>
              <div className="lab">امسح الهوية أو الإقامة</div>
              <div className="sub">Insert ID / Iqama into the reader</div>
            </div>
            <div className="fd-or">— أو —</div>
            <div className="dh-field" style={{flex: 1}}>
              <label>إدخال يدوي</label>
              <input placeholder="رقم الهوية / جواز / إقامة"/>
              <span className="hint">يدعم القارئ الذكي صور الهوية والمسح الضوئي تلقائياً.</span>
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="fd-guest">
            <div className="fd-guest-card">
              <div className="fd-photo">
                <svg viewBox="0 0 24 24" width="42" height="42" fill="none" stroke="currentColor" strokeWidth="1.25"><circle cx="12" cy="9" r="3"/><path d="M5.5 20a7 7 0 0 1 13 0"/></svg>
              </div>
              <div className="fd-guest-info">
                <div className="nm">أحمد بن سليمان الفهد</div>
                <div className="meta-grid">
                  <div className="cell"><div className="k">الهوية</div><div className="v en-num">1028456789</div></div>
                  <div className="cell"><div className="k">الجنسية</div><div className="v">سعودي 🇸🇦</div></div>
                  <div className="cell"><div className="k">تاريخ الميلاد</div><div className="v en-num">1985-06-12</div></div>
                  <div className="cell"><div className="k">الجوال</div><div className="v en-num">+966 50 482 1108</div></div>
                </div>
                <div className="fd-trust">
                  <span className="dh-pill gold">✦ ضيف متكرر — ٤ إقامات سابقة</span>
                  <span className="dh-pill ok"><NzIcon.shield/>تم التحقق</span>
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {step === 3 ? (
          <div className="fd-rooms">
            <div className="fd-rooms-head">
              <span>غرف متاحة — جناح ملكي</span>
              <div className="fd-filters">
                <button className="dh-chip is-on">ملكي</button>
                <button className="dh-chip">جناح</button>
                <button className="dh-chip">ديلوكس</button>
              </div>
            </div>
            <div className="fd-room-grid">
              {[
                { n: "٤٠١", view: "إطلالة بحرية", price: "١٬٢٠٠", status: "ready" },
                { n: "٤٠٢", view: "إطلالة بحرية", price: "١٬٢٠٠", status: "selected" },
                { n: "٤٠٣", view: "إطلالة بحرية", price: "١٬٢٠٠", status: "ready" },
                { n: "٥٠١", view: "بنتهاوس", price: "٢٬٤٠٠", status: "vip" },
                { n: "٥٠٢", view: "بنتهاوس", price: "٢٬٤٠٠", status: "cleaning" },
              ].map(r => (
                <div key={r.n} className={"fd-room " + (r.status === "selected" ? "is-on" : "") + (r.status === "cleaning" ? " is-disabled" : "")}>
                  <div className="rn">{r.n}</div>
                  <div className="rv">{r.view}</div>
                  <div className="rp"><span className="v">{r.price}</span><span className="cur">ر.س / ليلة</span></div>
                  {r.status === "cleaning" ? <span className="rb">قيد التنظيف</span> : null}
                  {r.status === "vip" ? <span className="rb gold">VIP</span> : null}
                  {r.status === "selected" ? <span className="rb on"><NzIcon.check/></span> : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div className="fd-foot">
        {step > 1 ? <button className="dh-btn is-ghost" onClick={() => setStep(step - 1)}>السابق</button> : <span/>}
        {step < 3
          ? <button className="dh-btn is-primary" onClick={() => setStep(step + 1)}>التالي ←</button>
          : <button className="dh-btn is-gold"><NzIcon.key/>إصدار المفتاح وتسجيل الدخول</button>}
      </div>
    </div>
  );
}

window.CheckInPanel = CheckInPanel;
