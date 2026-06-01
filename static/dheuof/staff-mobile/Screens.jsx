/* @jsx React.createElement */
/* global React, NzIcon */
const { useState, useEffect } = React;

/* ══ i18n ══════════════════════════════════════════════════════════════════ */
const T = {
  ar:{ flag:'🇸🇦',name:'العربية',dir:'rtl',
    nav_home:'الرئيسية',nav_tasks:'المهام',nav_rooms:'الغرف',nav_msgs:'رسائل',nav_me:'حسابي',
    checkin:'تسجيل الحضور',checkout_att:'تسجيل الانصراف',
    greet_m:'صباح الخير',greet_e:'مساء الخير',
    gps_ok:'مفعّل — فندق ضيوف الرياض',
    tasks_lbl:'مهمة اليوم',done_lbl:'منجزة',cleaned_lbl:'غرفة نُظِّفت',hrs_lbl:'ساعة عمل',
    schedule_title:'جدول اليوم',
    next_shift:'الوردية القادمة',meal_time:'وقت الوجبة',shift_end:'نهاية الوردية',
    filter_all:'الكل',filter_pend:'معلقة',filter_prog:'جارية',filter_done:'منتهية',
    task_vip:'VIP ✦',task_urgent:'عاجل',task_photo:'أضف صورة إنجاز',task_pause:'إيقاف',task_complete:'إكمال المهمة',
    confirm_title:'تأكيد تسجيل الخروج',
    confirm_body:'يجب التحقق من نظافة الغرفة قبل تسجيل خروج الضيف.',
    confirm_chk:'الغرفة نظيفة وجاهزة للضيف القادم',
    confirm_ok:'تأكيد الخروج',cancel:'إلغاء',
    toast_checkout:'✓ تسجيل الخروج — الغرفة حُوِّلت للتنظيف',
    toast_checkin:'✓ تم تسجيل الحضور',toast_checkout_att:'✓ تم تسجيل الانصراف',toast_task_done:'✓ تم إكمال المهمة',
    room_occ:'مشغولة',room_checkout:'مغادرة',room_clean:'تنظيف',room_ready:'جاهزة',room_block:'محظورة',
    msg_notif:'إشعارات',msg_chat:'دردشة',lang_title:'لغة التطبيق',
    pts_title:'نقاطي هذا الشهر',rating_title:'الأداء الأسبوعي',bonus_title:'الحوافز',schedule_title2:'جدولي القادم',
    emp_name:'ماريا سانتوس',emp_role:'مشرفة التدبير المنزلي',
  },
  en:{ flag:'🇬🇧',name:'English',dir:'ltr',
    nav_home:'Home',nav_tasks:'Tasks',nav_rooms:'Rooms',nav_msgs:'Inbox',nav_me:'Profile',
    checkin:'Clock In',checkout_att:'Clock Out',
    greet_m:'Good Morning',greet_e:'Good Evening',
    gps_ok:'Active — Dheuof Hotel Riyadh',
    tasks_lbl:'Tasks Today',done_lbl:'Done',cleaned_lbl:'Rooms Cleaned',hrs_lbl:'Hours',
    schedule_title:"Today's Schedule",
    next_shift:'Next Shift',meal_time:'Meal Time',shift_end:'Shift End',
    filter_all:'All',filter_pend:'Pending',filter_prog:'In Progress',filter_done:'Done',
    task_vip:'VIP ✦',task_urgent:'Urgent',task_photo:'Add Photo',task_pause:'Pause',task_complete:'Complete Task',
    confirm_title:'Confirm Checkout',
    confirm_body:'Room cleanliness must be verified before guest checkout.',
    confirm_chk:'Room is clean and ready for next guest',
    confirm_ok:'Confirm Checkout',cancel:'Cancel',
    toast_checkout:'✓ Room checked out — assigned to cleaning',
    toast_checkin:'✓ Clocked in',toast_checkout_att:'✓ Clocked out',toast_task_done:'✓ Task completed',
    room_occ:'Occupied',room_checkout:'Checkout',room_clean:'Cleaning',room_ready:'Ready',room_block:'Blocked',
    msg_notif:'Alerts',msg_chat:'Chat',lang_title:'App Language',
    pts_title:'My Points This Month',rating_title:'Weekly Performance',bonus_title:'Incentives',schedule_title2:'Upcoming Schedule',
    emp_name:'Maria Santos',emp_role:'Housekeeping Supervisor',
  },
  hi:{ flag:'🇮🇳',name:'हिन्दी',dir:'ltr',
    nav_home:'होम',nav_tasks:'कार्य',nav_rooms:'कमरे',nav_msgs:'संदेश',nav_me:'प्रोफाइल',
    checkin:'उपस्थिति दर्ज',checkout_att:'प्रस्थान दर्ज',
    greet_m:'सुप्रभात',greet_e:'शुभ संध्या',
    gps_ok:'सक्रिय — ध्यूफ होटल',
    tasks_lbl:'आज के कार्य',done_lbl:'पूर्ण',cleaned_lbl:'कमरे साफ',hrs_lbl:'घंटे',
    schedule_title:'आज का कार्यक्रम',
    next_shift:'अगली शिफ्ट',meal_time:'खाने का समय',shift_end:'शिफ्ट समाप्त',
    filter_all:'सभी',filter_pend:'लंबित',filter_prog:'जारी',filter_done:'पूर्ण',
    task_vip:'VIP ✦',task_urgent:'अत्यावश्यक',task_photo:'फोटो जोड़ें',task_pause:'रोकें',task_complete:'पूर्ण करें',
    confirm_title:'चेकआउट की पुष्टि',
    confirm_body:'मेहमान चेकआउट से पहले कमरे की सफाई अनिवार्य है।',
    confirm_chk:'कमरा साफ और तैयार है',
    confirm_ok:'पुष्टि करें',cancel:'रद्द',
    toast_checkout:'✓ चेकआउट — सफाई के लिए भेजा',
    toast_checkin:'✓ उपस्थिति दर्ज',toast_checkout_att:'✓ प्रस्थान दर्ज',toast_task_done:'✓ कार्य पूर्ण',
    room_occ:'व्यस्त',room_checkout:'चेकआउट',room_clean:'सफाई',room_ready:'तैयार',room_block:'अवरुद्ध',
    msg_notif:'सूचनाएं',msg_chat:'चैट',lang_title:'ऐप भाषा',
    pts_title:'इस महीने मेरे अंक',rating_title:'साप्ताहिक प्रदर्शन',bonus_title:'प्रोत्साहन',schedule_title2:'आगामी अनुसूची',
    emp_name:'Maria Santos',emp_role:'हाउसकीपिंग पर्यवेक्षक',
  },
  ne:{ flag:'🇳🇵',name:'नेपाली',dir:'ltr',
    nav_home:'गृह',nav_tasks:'कार्यहरू',nav_rooms:'कोठाहरू',nav_msgs:'सन्देश',nav_me:'प्रोफाइल',
    checkin:'हाजिरी गर्नुस्',checkout_att:'प्रस्थान गर्नुस्',
    greet_m:'शुभ प्रभात',greet_e:'शुभ सन्ध्या',
    gps_ok:'सक्रिय — ध्यूफ होटल',
    tasks_lbl:'आजका कार्य',done_lbl:'पूर्ण',cleaned_lbl:'सफा कोठा',hrs_lbl:'घण्टा',
    schedule_title:'आजको तालिका',
    next_shift:'अर्को सिफ्ट',meal_time:'खाना समय',shift_end:'सिफ्ट अन्त्य',
    filter_all:'सबै',filter_pend:'पर्खिरहेको',filter_prog:'जारी',filter_done:'पूर्ण',
    task_vip:'VIP ✦',task_urgent:'अत्यावश्यक',task_photo:'फोटो थप्नुस्',task_pause:'रोक्नुस्',task_complete:'पूर्ण गर्नुस्',
    confirm_title:'चेकआउट पुष्टि',
    confirm_body:'पाहुना चेकआउट अघि कोठा सफा छ भनी पुष्टि गर्नुपर्छ।',
    confirm_chk:'कोठा सफा र तयार छ',
    confirm_ok:'पुष्टि गर्नुस्',cancel:'रद्द',
    toast_checkout:'✓ चेकआउट — सफाईका लागि पठाइयो',
    toast_checkin:'✓ हाजिरी दर्ता',toast_checkout_att:'✓ प्रस्थान दर्ता',toast_task_done:'✓ कार्य पूर्ण',
    room_occ:'व्यस्त',room_checkout:'चेकआउट',room_clean:'सफाई',room_ready:'तयार',room_block:'अवरुद्ध',
    msg_notif:'सूचनाहरू',msg_chat:'च्याट',lang_title:'एप भाषा',
    pts_title:'यो महिना मेरा अंक',rating_title:'साप्ताहिक प्रदर्शन',bonus_title:'प्रोत्साहन',schedule_title2:'आगामी तालिका',
    emp_name:'Maria Santos',emp_role:'हाउसकीपिङ सुपरभाइजर',
  },
  tl:{ flag:'🇵🇭',name:'Filipino',dir:'ltr',
    nav_home:'Home',nav_tasks:'Gawain',nav_rooms:'Silid',nav_msgs:'Mensahe',nav_me:'Profile',
    checkin:'Mag-clock in',checkout_att:'Mag-clock out',
    greet_m:'Magandang umaga',greet_e:'Magandang gabi',
    gps_ok:'Aktibo — Dheuof Hotel',
    tasks_lbl:'Gawain ngayon',done_lbl:'Tapos',cleaned_lbl:'Silid nalinis',hrs_lbl:'Oras',
    schedule_title:'Iskedyul ngayon',
    next_shift:'Susunod na shift',meal_time:'Oras ng pagkain',shift_end:'Katapusan',
    filter_all:'Lahat',filter_pend:'Nakabinbin',filter_prog:'Sa progreso',filter_done:'Tapos',
    task_vip:'VIP ✦',task_urgent:'Apurahan',task_photo:'Magdagdag ng larawan',task_pause:'I-pause',task_complete:'Tapusin',
    confirm_title:'Kumpirmahin ang Checkout',
    confirm_body:'Dapat kumpirmahin ang kalinisan ng silid bago mag-checkout.',
    confirm_chk:'Malinis at handa ang silid',
    confirm_ok:'Kumpirmahin',cancel:'Kanselahin',
    toast_checkout:'✓ Na-checkout — para sa paglilinis',
    toast_checkin:'✓ Naka-clock in',toast_checkout_att:'✓ Naka-clock out',toast_task_done:'✓ Tapos na',
    room_occ:'Abala',room_checkout:'Checkout',room_clean:'Naglilinis',room_ready:'Handa',room_block:'Naharang',
    msg_notif:'Alerto',msg_chat:'Chat',lang_title:'Wika ng App',
    pts_title:'Aking Puntos ngayong Buwan',rating_title:'Lingguhang Pagganap',bonus_title:'Mga Bonus',schedule_title2:'Paparating na Iskedyul',
    emp_name:'Maria Santos',emp_role:'Housekeeping Supervisor',
  },
  bn:{ flag:'🇧🇩',name:'বাংলা',dir:'ltr',
    nav_home:'হোম',nav_tasks:'কাজ',nav_rooms:'রুম',nav_msgs:'বার্তা',nav_me:'প্রোফাইল',
    checkin:'উপস্থিতি নিবন্ধন',checkout_att:'প্রস্থান নিবন্ধন',
    greet_m:'শুভ সকাল',greet_e:'শুভ সন্ধ্যা',
    gps_ok:'সক্রিয় — ধুওফ হোটেল',
    tasks_lbl:'আজকের কাজ',done_lbl:'সম্পন্ন',cleaned_lbl:'রুম পরিষ্কার',hrs_lbl:'ঘণ্টা',
    schedule_title:'আজকের সময়সূচি',
    next_shift:'পরবর্তী শিফট',meal_time:'খাবার সময়',shift_end:'শিফট শেষ',
    filter_all:'সব',filter_pend:'মুলতুবি',filter_prog:'চলছে',filter_done:'সম্পন্ন',
    task_vip:'VIP ✦',task_urgent:'জরুরি',task_photo:'ছবি যোগ করুন',task_pause:'বিরতি',task_complete:'সম্পন্ন করুন',
    confirm_title:'চেকআউট নিশ্চিত করুন',
    confirm_body:'অতিথি চেকআউটের আগে রুম পরিষ্কার নিশ্চিত করতে হবে।',
    confirm_chk:'রুম পরিষ্কার ও প্রস্তুত',
    confirm_ok:'নিশ্চিত করুন',cancel:'বাতিল',
    toast_checkout:'✓ চেকআউট — পরিষ্কারের জন্য পাঠানো হয়েছে',
    toast_checkin:'✓ উপস্থিতি নিবন্ধিত',toast_checkout_att:'✓ প্রস্থান নিবন্ধিত',toast_task_done:'✓ কাজ সম্পন্ন',
    room_occ:'ব্যস্ত',room_checkout:'চেকআউট',room_clean:'পরিষ্কার',room_ready:'প্রস্তুত',room_block:'অবরুদ্ধ',
    msg_notif:'বিজ্ঞপ্তি',msg_chat:'চ্যাট',lang_title:'অ্যাপের ভাষা',
    pts_title:'এই মাসে আমার পয়েন্ট',rating_title:'সাপ্তাহিক কর্মক্ষমতা',bonus_title:'প্রণোদনা',schedule_title2:'আসন্ন সময়সূচি',
    emp_name:'Maria Santos',emp_role:'হাউসকিপিং সুপারভাইজার',
  },
};

/* ══ Static data ════════════════════════════════════════════════════════════ */
const ROOMS_INIT = [
  { id:'101', type:'ستاندرد', floor:1, status:'occ',      guest:'سالم المطيري',  due:null    },
  { id:'102', type:'ديلوكس',  floor:1, status:'ready',    guest:null,             due:null    },
  { id:'103', type:'ديلوكس',  floor:1, status:'checkout', guest:'أحمد الحربي',   due:'11:00' },
  { id:'104', type:'ستاندرد', floor:1, status:'clean',    guest:null,             due:null    },
  { id:'105', type:'ستاندرد', floor:1, status:'ready',    guest:null,             due:null    },
  { id:'201', type:'جناح',    floor:2, status:'occ',      guest:'رنا العبدلي',    due:null    },
  { id:'202', type:'ديلوكس',  floor:2, status:'checkout', guest:'فهد السبيعي',   due:'12:00' },
  { id:'203', type:'ستاندرد', floor:2, status:'clean',    guest:null,             due:null    },
  { id:'204', type:'ستاندرد', floor:2, status:'block',    guest:null,             due:null    },
  { id:'205', type:'ديلوكس',  floor:2, status:'ready',    guest:null,             due:null    },
  { id:'301', type:'جناح ملكي',floor:3,status:'occ',      guest:'بندر الدوسري',  due:null    },
  { id:'302', type:'جناح',    floor:3, status:'occ',      guest:'منى القحطاني',  due:null    },
  { id:'303', type:'ديلوكس',  floor:3, status:'clean',    guest:null,             due:null    },
  { id:'304', type:'ستاندرد', floor:3, status:'ready',    guest:null,             due:null    },
];

const TASKS_INIT = [
  { id:1, room:'٤٠٢', type:'جناح ملكي', status:'in', prio:'vip', notes:'تنظيف عميق · وسائد إضافية', est:'٤٥ د',
    checks:[
      {d:true, ar:'تجديد الفراش — قطن مصري كينج'},
      {d:true, ar:'تنظيف الحمامات + إعادة تجهيز'},
      {d:true, ar:'تجديد المناشف الكبيرة والصغيرة'},
      {d:false,ar:'تنظيف عميق للسجاد'},
      {d:false,ar:'تجديد عطر التوقيع — Dheuof Signature'},
      {d:false,ar:'وسائد إضافية × ٢ (طلب الضيف)'},
    ],
    guest_note:'"وسائد إضافية للسرير الرئيسي. الفطور الساعة ٨ صباحاً."',
    guest_name:'أحمد بن سليمان الفهد',
  },
  {id:2,room:'٢١٨',type:'ديلوكس',    status:'ready',  prio:'normal',notes:'تنظيف بعد المغادرة',   est:'٢٥ د',checks:[],guest_note:null},
  {id:3,room:'٣٠٧',type:'ديلوكس',    status:'ready',  prio:'high',  notes:'تنظيف + تجديد عطر',   est:'٣٠ د',checks:[],guest_note:null},
  {id:4,room:'٤١٠',type:'جناح',      status:'blocked',prio:'high',  notes:'بانتظار صيانة المكيف',est:'—',   checks:[],guest_note:null},
  {id:5,room:'١٠٤',type:'ستاندرد',   status:'ready',  prio:'normal',notes:'تنظيف يومي',           est:'٢٠ د',checks:[],guest_note:null},
  {id:6,room:'٢٢١',type:'ديلوكس',    status:'done',   prio:'normal',notes:'اكتمل قبل ١٢ دقيقة',  est:'تم',  checks:[],guest_note:null},
];

const NOTIFS = [
  {id:1,type:'shift',ic:'⏰',ar:'بداية الوردية الصباحية',en:'Morning shift starts',time:'08:00',unread:false},
  {id:2,type:'task', ic:'✅',ar:'مهمة جديدة: غرفة ٣٠٧ تنظيف عميق',en:'New task: Room 307 deep clean',time:'08:15',unread:true},
  {id:3,type:'mgmt', ic:'📋',ar:'تذكير: اجتماع الوردية الساعة ١٤:٠٠',en:'Shift meeting at 14:00',time:'08:30',unread:true},
  {id:4,type:'meal', ic:'🍽',ar:'وقت الغداء ١٣:٠٠ — مطبخ الموظفين',en:'Lunch 13:00 — Staff kitchen',time:'09:00',unread:false},
  {id:5,type:'maint',ic:'🔧',ar:'طلب صيانة: غرفة ٢٠٤ — مكيف',en:'Maintenance: Room 204 — AC',time:'09:22',unread:true},
  {id:6,type:'mgmt', ic:'🏆',ar:'تهانينا ماريا! أفضل موظفة الأسبوع',en:'Congrats Maria! Employee of the week',time:'أمس',unread:false},
];

const CHAT = [
  {id:1,from:'أحمد المشرف',mine:false,msg:'ماريا، الغرفة ٤٠٢ أولوية قبل ١١',time:'٠٨:٤٠'},
  {id:2,from:'أنا',         mine:true, msg:'فهمت، بدأت للتو',               time:'٠٨:٤٢'},
  {id:3,from:'نورة الهاشمي',mine:false,msg:'من يغطي الطابق ٣ اليوم؟',      time:'٠٨:٥٥'},
  {id:4,from:'أنا',         mine:true, msg:'أنا سأغطيه بعد ٤٠٢',           time:'٠٨:٥٦'},
];

/* ══ Status config ══════════════════════════════════════════════════════════ */
function sCfg(status) {
  return {
    occ:     {bg:'#1B4D3D',fg:'#fff',light:'#E5F4EC'},
    checkout:{bg:'#C9A85F',fg:'#fff',light:'#FDF5E6'},
    clean:   {bg:'#3B82C4',fg:'#fff',light:'#E3EEF8'},
    ready:   {bg:'#2E7D5E',fg:'#fff',light:'#E5F4EC'},
    block:   {bg:'#C0392B',fg:'#fff',light:'#FDECEA'},
  }[status] || {bg:'#888',fg:'#fff',light:'#eee'};
}

/* ══ Toast ══════════════════════════════════════════════════════════════════ */
function Toast({msg,onDone}) {
  useEffect(()=>{ const t=setTimeout(onDone,2800); return ()=>clearTimeout(t); },[]);
  return <div className="sm-toast">{msg}</div>;
}

/* ══ Bottom Nav ═════════════════════════════════════════════════════════════ */
function BottomNav({tab,setTab,t,unread}) {
  const items = [
    {key:'home', e:'⊙', l:t.nav_home},
    {key:'tasks',e:'✓', l:t.nav_tasks},
    {key:'rooms',e:'▦', l:t.nav_rooms},
    {key:'msgs', e:'✉', l:t.nav_msgs, badge:unread},
    {key:'me',   e:'◉', l:t.nav_me},
  ];
  return (
    <div className="sm-bottom-nav">
      {items.map(it=>(
        <button key={it.key} className={'sm-bnav-btn'+(tab===it.key?' is-on':'')} onClick={()=>setTab(it.key)}>
          <span className="sm-bnav-ic">{it.e}</span>
          {it.badge>0 && <span className="sm-bnav-dot"/>}
          <span className="sm-bnav-lbl">{it.l}</span>
        </button>
      ))}
    </div>
  );
}

/* ══ Screen 1 — Home ════════════════════════════════════════════════════════ */
function HomeScreen({t,checkedIn,onToggle,sinceTime}) {
  const hr = new Date().getHours();
  const greet = hr<12 ? t.greet_m : t.greet_e;
  const kpis = [{v:'١٢',l:t.tasks_lbl},{v:'٥',l:t.done_lbl},{v:'٤',l:t.cleaned_lbl},{v:'٧.٣',l:t.hrs_lbl}];
  const sched = [
    {ic:'🔔',l:t.next_shift, v:'٠٨:٠٠',type:'shift'},
    {ic:'🍽',l:t.meal_time,  v:'١٣:٠٠',type:'meal'},
    {ic:'🌙',l:t.shift_end,  v:'١٦:٠٠',type:'end'},
  ];
  return (
    <div className="sm-screen sm-home">
      <div className="sm-gps-bar"><span className="gps-dot"/><span>📍 {t.gps_ok}</span></div>
      <div className="sm-home-hero">
        <div>
          <div className="sm-greet">{greet}، ماريا 👋</div>
          <div className="sm-role">{t.emp_role}</div>
        </div>
        <button className={'sm-attend-btn'+(checkedIn?' is-out':'')} onClick={onToggle}>
          <div className="at-ic">⏱</div>
          <div className="at-main">{checkedIn?t.checkout_att:t.checkin}</div>
          {checkedIn&&sinceTime&&<div className="at-sub">منذ {sinceTime}</div>}
          <div className="at-hint">GPS + بصمة ذكية</div>
        </button>
      </div>
      <div className="sm-home-kpis">
        {kpis.map((k,i)=><div key={i} className="sm-hkpi"><div className="v">{k.v}</div><div className="l">{k.l}</div></div>)}
      </div>
      <div className="sm-section-title">{t.schedule_title}</div>
      <div className="sm-sched-list">
        {sched.map((s,i)=>(
          <div key={i} className={'sm-sched-item t-'+s.type}>
            <span className="si-ic">{s.ic}</span>
            <span className="si-lbl">{s.l}</span>
            <span className="si-val">{s.v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ══ Screen 2 — Tasks ═══════════════════════════════════════════════════════ */
function TasksScreen({t,tasks,setTasks,onToast}) {
  const [filter,setFilter] = useState('all');
  const [activeId,setActiveId] = useState(null);

  const fkeys  = ['all','ready','in','done'];
  const flbls  = [t.filter_all,t.filter_pend,t.filter_prog,t.filter_done];
  const sMap   = {
    in:     {bg:'linear-gradient(135deg,#C9A85F,#9A7430)',fg:'#fff',ar:'قيد العمل'},
    ready:  {bg:'#fff',fg:'#1B4D3D',ar:'جاهزة'},
    blocked:{bg:'#FDECEA',fg:'#C0392B',ar:'محظورة'},
    done:   {bg:'#E5F4EC',fg:'#1A5C3A',ar:'تم'},
  };

  const filtered = tasks.filter(tk=>filter==='all'||tk.status===filter);
  const active   = tasks.find(tk=>tk.id===activeId);

  if (active) return <TaskDetail t={t} task={active} tasks={tasks} setTasks={setTasks} onBack={()=>setActiveId(null)} onToast={onToast}/>;

  return (
    <div className="sm-screen">
      <div className="sm-screen-head">
        <div className="sm-screen-title">قائمة المهام</div>
        <div className="sm-prog-mini"><div className="bar"><div className="fill" style={{width:'42%'}}/></div><span>٥/١٢</span></div>
      </div>
      <div className="sm-filter-bar">
        {fkeys.map((k,i)=><button key={k} className={'sm-fbtn'+(filter===k?' is-on':'')} onClick={()=>setFilter(k)}>{flbls[i]}</button>)}
      </div>
      <div className="sm-list">
        {filtered.map(tk=>{
          const s=sMap[tk.status]||sMap.ready;
          return (
            <div key={tk.id} className={'sm-task '+tk.status} onClick={()=>setActiveId(tk.id)}>
              <div className="sm-room" style={{background:s.bg,color:s.fg}}>
                <div className="n">{tk.room}</div><div className="ty">{tk.type}</div>
              </div>
              <div className="sm-body">
                <div className="hd">
                  <span className="st">{s.ar}</span>
                  {tk.prio==='vip'  &&<span className="prio vip">{t.task_vip}</span>}
                  {tk.prio==='high' &&<span className="prio hi">{t.task_urgent}</span>}
                </div>
                <div className="nt">{tk.notes}</div>
                <div className="ft">⏱ <span>{tk.est}</span></div>
              </div>
              <div className="sm-go">›</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TaskDetail({t,task,tasks,setTasks,onBack,onToast}) {
  const [checks,setChecks] = useState(task.checks||[]);
  const [photo,setPhoto]   = useState(false);
  const done  = checks.filter(c=>c.d).length;
  const total = checks.length;
  const toggle = i => setChecks(checks.map((c,j)=>j===i?{...c,d:!c.d}:c));
  const complete = () => {
    setTasks(tasks.map(tk=>tk.id===task.id?{...tk,status:'done',checks}:tk));
    onToast(t.toast_task_done); onBack();
  };
  return (
    <div className="sm-screen">
      <div className="sm-detail-hd">
        <button className="sm-back" onClick={onBack}>‹</button>
        <span>غرفة {task.room} · {task.type}</span>
        {task.prio==='vip'&&<span className="vipd">{t.task_vip}</span>}
      </div>
      <div className="sm-detail-body">
        <div className="sm-stage-card">
          <div className="ttl">قائمة المهام</div>
          <div className="meta">{total} مهام · {task.est} · {done}/{total} مكتمل</div>
          {total>0&&<div className="prog-bar"><div className="prog-fill" style={{width:total?(done/total*100)+'%':'0%'}}/></div>}
        </div>
        {checks.length>0&&(
          <div className="sm-checks">
            {checks.map((c,i)=>(
              <label key={i} className={'sm-check '+(c.d?'is-on':'')} onClick={()=>toggle(i)}>
                <span className="box">{c.d?'✓':''}</span>
                <span className="lbl">{c.ar}</span>
              </label>
            ))}
          </div>
        )}
        {task.guest_note&&(
          <div className="sm-notes-card">
            <div className="nl">ملاحظات النزيل</div>
            <div className="nb">{task.guest_note}</div>
            <div className="nf">— {task.guest_name}</div>
          </div>
        )}
        <button className={'sm-photo-btn'+(photo?' is-added':'')} onClick={()=>setPhoto(true)}>
          {photo?'✓ تمت إضافة الصورة':('📷 '+t.task_photo)}
        </button>
      </div>
      <div className="sm-foot">
        <button className="sm-act-2" onClick={onBack}>{t.task_pause}</button>
        <button className="sm-act-1" onClick={complete}>{t.task_complete}</button>
      </div>
    </div>
  );
}

/* ══ Screen 3 — Rooms ═══════════════════════════════════════════════════════ */
function RoomsScreen({t,rooms,setRooms,onToast}) {
  const [filter,setFilter]     = useState('all');
  const [confirm,setConfirm]   = useState(null);
  const [chkd,setChkd]         = useState(false);

  const statuses = ['all','occ','checkout','clean','ready','block'];
  const lbl = s=>({all:'الكل',occ:t.room_occ,checkout:t.room_checkout,clean:t.room_clean,ready:t.room_ready,block:t.room_block})[s];
  const counts = {};
  rooms.forEach(r=>{ counts[r.status]=(counts[r.status]||0)+1; });
  const filtered = rooms.filter(r=>filter==='all'||r.status===filter);

  const doCheckout = () => {
    if(!chkd) return;
    setRooms(rooms.map(r=>r.id===confirm.id?{...r,status:'clean',guest:null,due:null}:r));
    onToast(t.toast_checkout); setConfirm(null);
  };

  return (
    <div className="sm-screen">
      <div className="sm-screen-head">
        <div className="sm-screen-title">إدارة الغرف</div>
        <div className="sm-room-summary">
          <span className="rs rs-occ">{counts.occ||0} {t.room_occ}</span>
          <span className="rs rs-co">{counts.checkout||0} {t.room_checkout}</span>
        </div>
      </div>
      <div className="sm-filter-bar sm-filter-scroll">
        {statuses.map(s=>(
          <button key={s} className={'sm-fbtn'+(filter===s?' is-on':'')} onClick={()=>setFilter(s)}>
            {lbl(s)}{s!=='all'&&counts[s]?<span className="fct"> {counts[s]}</span>:null}
          </button>
        ))}
      </div>
      <div className="sm-rooms-grid">
        {filtered.map(room=>{
          const c=sCfg(room.status); const isCo=room.status==='checkout';
          return (
            <div key={room.id} className={'sm-room-card'+(isCo?' is-tap':'')} style={{background:c.light,borderColor:c.bg+'44'}} onClick={()=>isCo&&(setConfirm(room),setChkd(false))}>
              <div className="rc-top">
                <div className="rc-num">{room.id}</div>
                <div className="rc-badge" style={{background:c.bg}}>{lbl(room.status)}</div>
              </div>
              <div className="rc-type">{room.type} · ط{room.floor}</div>
              {room.guest&&<div className="rc-guest">👤 {room.guest}</div>}
              {room.due  &&<div className="rc-due">🕐 {room.due}</div>}
              {isCo&&<div className="rc-hint">اضغط للتسجيل ▼</div>}
            </div>
          );
        })}
      </div>

      {confirm&&(
        <div className="sm-overlay" onClick={()=>setConfirm(null)}>
          <div className="sm-modal" onClick={e=>e.stopPropagation()}>
            <div className="sm-modal-ic">🏨</div>
            <div className="sm-modal-title">{t.confirm_title}</div>
            <div className="sm-modal-room">غرفة {confirm.id} · {confirm.type}</div>
            {confirm.guest&&<div className="sm-modal-guest">👤 {confirm.guest}</div>}
            <div className="sm-modal-body">{t.confirm_body}</div>
            <label className={'sm-modal-chk'+(chkd?' is-on':'')} onClick={()=>setChkd(!chkd)}>
              <span className="box">{chkd?'✓':''}</span>
              <span className="lbl">{t.confirm_chk}</span>
            </label>
            <div className="sm-modal-acts">
              <button className="sm-modal-cancel" onClick={()=>setConfirm(null)}>{t.cancel}</button>
              <button className={'sm-modal-ok'+(chkd?'':' disabled')} onClick={doCheckout}>{t.confirm_ok}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ══ Screen 4 — Messages ════════════════════════════════════════════════════ */
function MessagesScreen({t,lang,setLang}) {
  const [tab,setTab]     = useState('notif');
  const [notifs,setNotifs] = useState(NOTIFS);
  const unread = notifs.filter(n=>n.unread).length;
  const tColor = {shift:'#1B4D3D',task:'#2E7D5E',mgmt:'#7A4800',meal:'#B5451B',maint:'#1A4E7A'};

  return (
    <div className="sm-screen">
      <div className="sm-screen-head">
        <div className="sm-screen-title">الإشعارات والرسائل</div>
        {unread>0&&<div className="sm-ubadge">{unread}</div>}
      </div>
      <div className="sm-lang-bar">
        <span className="sm-lang-lbl">{t.lang_title}</span>
        <div className="sm-lang-pills">
          {Object.entries(T).map(([code,lv])=>(
            <button key={code} className={'sm-lpill'+(lang===code?' is-on':'')} onClick={()=>setLang(code)}>{lv.flag}</button>
          ))}
        </div>
      </div>
      <div className="sm-msg-tabs">
        <button className={'sm-mtab'+(tab==='notif'?' is-on':'')} onClick={()=>setTab('notif')}>
          {t.msg_notif}{unread>0&&<span className="ct"> {unread}</span>}
        </button>
        <button className={'sm-mtab'+(tab==='chat'?' is-on':'')} onClick={()=>setTab('chat')}>{t.msg_chat}</button>
      </div>
      {tab==='notif'?(
        <div className="sm-notif-list">
          {notifs.map(n=>(
            <div key={n.id} className={'sm-notif-item'+(n.unread?' is-unread':'')} onClick={()=>setNotifs(notifs.map(x=>x.id===n.id?{...x,unread:false}:x))}>
              <div className="ni-ic" style={{background:(tColor[n.type]||'#555')+'20',color:tColor[n.type]||'#555'}}>{n.ic}</div>
              <div className="ni-body">
                <div className="ni-text">{lang==='en'?n.en:n.ar}</div>
                <div className="ni-time">{n.time}</div>
              </div>
              {n.unread&&<div className="ni-dot"/>}
            </div>
          ))}
        </div>
      ):(
        <div className="sm-chat-list">
          {CHAT.map(m=>(
            <div key={m.id} className={'sm-chat-msg'+(m.mine?' is-mine':'')}>
              {!m.mine&&<div className="cm-from">{m.from}</div>}
              <div className="cm-bubble">{m.msg}</div>
              <div className="cm-time">{m.time}</div>
            </div>
          ))}
          <div className="sm-chat-input-row">
            <div className="sm-chat-input">اكتب رسالة...</div>
            <button className="sm-chat-send">↑</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ══ Screen 5 — Profile ═════════════════════════════════════════════════════ */
function ProfileScreen({t}) {
  const today = new Date().getDay();
  const dLabels=['ح','ن','ث','ر','خ','ج','س'];
  const bars   =[88,76,95,82,91,0,0];
  const schedule=[
    {day:'الاثنين', date:'٢ يونيو',  shift:'٠٨:٠٠–١٦:٠٠',type:'morning'},
    {day:'الثلاثاء',date:'٣ يونيو',  shift:'٠٨:٠٠–١٦:٠٠',type:'morning'},
    {day:'الأربعاء',date:'٤ يونيو',  shift:'يوم راحة',    type:'off'},
    {day:'الخميس',  date:'٥ يونيو',  shift:'١٢:٠٠–٢٠:٠٠',type:'mid'},
    {day:'الجمعة',  date:'٦ يونيو',  shift:'يوم راحة',    type:'off'},
  ];
  return (
    <div className="sm-screen sm-profile">
      <div className="sm-emp-card">
        <div className="sm-emp-av">م</div>
        <div className="sm-emp-info">
          <div className="nm">{t.emp_name}</div>
          <div className="rl">{t.emp_role}</div>
          <div className="sh">الوردية الصباحية · ٠٨:٠٠–١٦:٠٠</div>
        </div>
        <div className="sm-emp-star">★★★★★<div className="sv">٤.٨</div></div>
      </div>

      <div className="sm-section-title">{t.pts_title}</div>
      <div className="sm-pts-card">
        <div className="pt-main"><div className="pt-v">٢٤٥</div><div className="pt-l">نقطة</div></div>
        <div className="pt-rows">
          {[['الحضور','٨٠'],['المهام','١١٠'],['الجودة','٥٥']].map(([l,v],i)=>(
            <div key={i} className="pt-row"><span>{l}</span><span className="pv">{v}</span></div>
          ))}
        </div>
      </div>

      <div className="sm-section-title">{t.rating_title}</div>
      <div className="sm-week-bars">
        {dLabels.map((d,i)=>(
          <div key={i} className={'sm-wbar'+(i===today?' is-today':'')}>
            <div className="wb-fill" style={{height:bars[i]+'%',background:bars[i]===0?'#ddd':i===today?'#C9A85F':'#2E7D5E'}}/>
            <div className="wb-lbl">{d}</div>
          </div>
        ))}
      </div>

      <div className="sm-section-title">{t.bonus_title}</div>
      <div className="sm-bonus-list">
        {[['🏆','موظفة الأسبوع','+٥٠ ر.س'],['⭐','أداء ممتاز','+٣٠ ر.س'],['✅','حضور منتظم','+٢٠ ر.س']].map(([ic,l,v],i)=>(
          <div key={i} className="sm-bonus-item">
            <span className="bi-ic">{ic}</span><span className="bi-lbl">{l}</span><span className="bi-val">{v}</span>
          </div>
        ))}
      </div>

      <div className="sm-section-title">{t.schedule_title2}</div>
      <div className="sm-upcoming">
        {schedule.map((s,i)=>(
          <div key={i} className={'sm-urow t-'+s.type}>
            <div className="ur-day">{s.day}</div>
            <div className="ur-date">{s.date}</div>
            <div className={'ur-shift'+(s.type==='off'?' is-off':'')}>{s.shift}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ══ Main App ════════════════════════════════════════════════════════════════ */
function StaffApp({fullScreen}) {
  const [tab,setTab]         = useState('home');
  const [lang,setLang]       = useState('ar');
  const [checkedIn,setCI]    = useState(false);
  const [sinceTime,setSince] = useState(null);
  const [rooms,setRooms]     = useState(ROOMS_INIT);
  const [tasks,setTasks]     = useState(TASKS_INIT);
  const [toast,setToast]     = useState(null);
  const t   = T[lang];
  const dir = t.dir;

  const unread = NOTIFS.filter(n=>n.unread).length;

  const toggleCI = () => {
    if(!checkedIn){ setCI(true); setSince(new Date().toLocaleTimeString('ar-SA',{hour:'2-digit',minute:'2-digit'})); setToast(t.toast_checkin); }
    else          { setCI(false); setSince(null); setToast(t.toast_checkout_att); }
  };

  const wrapStyle = fullScreen
    ? {height:'100dvh',display:'flex',flexDirection:'column',background:'#F2F2F7',overflow:'hidden',direction:dir}
    : {height:'100%',  display:'flex',flexDirection:'column',background:'#F2F2F7',overflow:'hidden',direction:dir,paddingTop:56};

  return (
    <div style={wrapStyle}>
      <div style={{flex:1,overflowY:'auto',position:'relative'}}>
        {tab==='home' &&<HomeScreen     t={t} checkedIn={checkedIn} onToggle={toggleCI} sinceTime={sinceTime}/>}
        {tab==='tasks'&&<TasksScreen    t={t} tasks={tasks} setTasks={setTasks} onToast={setToast}/>}
        {tab==='rooms'&&<RoomsScreen    t={t} rooms={rooms} setRooms={setRooms} onToast={setToast}/>}
        {tab==='msgs' &&<MessagesScreen t={t} lang={lang} setLang={setLang}/>}
        {tab==='me'   &&<ProfileScreen  t={t}/>}
      </div>
      <BottomNav tab={tab} setTab={setTab} t={t} unread={unread}/>
      {toast&&<Toast msg={toast} onDone={()=>setToast(null)}/>}
    </div>
  );
}

window.StaffApp        = StaffApp;
window.TaskListScreen  = ()=>React.createElement(StaffApp,null);
window.TaskDetailScreen= ()=>React.createElement(StaffApp,null);
