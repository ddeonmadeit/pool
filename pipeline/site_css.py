"""Stylesheet for the SDL Finder site.

The visual language mirrors rawleads.org: a warm dark charcoal console with
cream text, a burnt-orange signal accent, bevelled keys and recessed wells.
Braun Linear is proprietary and self-hosted there, so Inter stands in for it -
it is the closest widely available neutral grotesque - with IBM Plex Mono for
tabular data.
"""

CSS = r"""
:root{
  --panel-900:#1c1b19; --panel-800:#242220; --panel-700:#2c2a27;
  --panel-600:#353330; --panel-500:#423f3b;
  --cream-100:#ece6da; --cream-300:#b9b2a4; --cream-500:#807a6e;
  --signal:#c5602c; --signal-dim:#7e4a2c; --signal-glow:#e0793f;
  --done:#7f8f6a; --red:#d05050; --faint:#5d574d;
  --edge-light:rgba(255,248,235,.06); --edge-dark:rgba(0,0,0,.45);
  --k-face-top:#3c3a35; --k-face-bot:#252320;
  --chassis-top:#322f2a; --chassis-mid:#2b2823; --chassis-bot:#262320;
  --ground:#272523;
  --row-h:48px; --pad:18px;
}
*{box-sizing:border-box;}
body{
  margin:0; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background-color:var(--ground);
  background-image:linear-gradient(90deg,rgba(255,248,235,.03) 25%,transparent 0);
  background-size:4px 4px;
  color:var(--cream-100); font-size:14px; line-height:1.55;
  letter-spacing:.01em; -webkit-font-smoothing:antialiased;
  min-height:100vh; overflow-x:hidden;
}
/* Film grain and vignette, straight from the reference's console feel. */
body::after{
  content:""; position:fixed; inset:0; pointer-events:none; z-index:9999; opacity:.055;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}
body::before{
  content:""; position:fixed; inset:0; pointer-events:none; z-index:9997;
  background:radial-gradient(ellipse 96% 84% at 50% 40%,transparent 56%,rgba(0,0,0,.30) 82%,rgba(0,0,0,.6) 100%);
}
.shell{max-width:1560px;margin:0 auto;padding:0 var(--pad) 80px;position:relative;z-index:1;}

/* ── Nav chassis ───────────────────────────────────────────────── */
.chassis{
  position:sticky; top:0; z-index:200; margin:0 calc(-1 * var(--pad)) 26px;
  padding:11px 22px;
  display:flex; align-items:center; gap:18px; flex-wrap:wrap;
  background:repeating-linear-gradient(90deg,rgba(255,248,235,.014) 0 1px,transparent 1px 3px),
             linear-gradient(180deg,var(--chassis-top) 0%,var(--chassis-mid) 26%,var(--chassis-bot) 100%);
  box-shadow:inset 0 2px 0 rgba(255,248,235,.11), inset 0 0 0 1px rgba(0,0,0,.3),
             0 4px 18px rgba(0,0,0,.5);
}
.brand{font-size:.92rem;font-weight:800;letter-spacing:.16em;text-transform:uppercase;}
.brand i{font-style:normal;color:var(--signal-glow);text-shadow:0 0 9px rgba(255,120,45,.45);}
.chassis .spacer{flex:1;}
.pagetag{font-family:"IBM Plex Mono",monospace;font-size:.6rem;font-weight:600;
  letter-spacing:.16em;text-transform:uppercase;color:var(--cream-300);
  padding:5px 11px;border-radius:6px;background:rgba(0,0,0,.22);
  box-shadow:inset 0 1px 0 rgba(255,248,235,.05);}

/* ── Stat row ──────────────────────────────────────────────────── */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:2px;
  border-radius:12px;overflow:hidden;margin-bottom:26px;
  box-shadow:inset 0 0 0 1px rgba(0,0,0,.45),0 1px 0 var(--edge-light);}
.stat{background:linear-gradient(180deg,var(--panel-800),var(--panel-900));
  padding:18px 16px;text-align:center;}
.stat .v{font-size:1.95rem;font-weight:900;letter-spacing:-.02em;line-height:1;
  margin-bottom:5px;font-variant-numeric:tabular-nums;color:#ffbe85;
  text-shadow:0 0 18px rgba(232,118,52,.5),0 0 5px rgba(255,150,80,.28);}
.stat .k{font-size:.56rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;
  color:var(--cream-500);}
.stat.g .v{color:#b9cf9a;text-shadow:0 0 16px rgba(127,143,106,.45);}
.stat.n .v{color:var(--cream-100);text-shadow:none;}

/* ── Keys and controls ─────────────────────────────────────────── */
.key{
  position:relative;border:none;cursor:pointer;color:var(--cream-300);
  background:linear-gradient(180deg,var(--k-face-top),var(--k-face-bot));
  display:inline-flex;align-items:center;justify-content:center;
  font-family:Inter,sans-serif;padding:0 15px;height:38px;border-radius:9px;
  font-weight:700;letter-spacing:.1em;text-transform:uppercase;font-size:.62rem;
  white-space:nowrap;text-decoration:none;
  box-shadow:inset 0 1px 0 rgba(255,248,235,.16),inset 0 -2px 0 rgba(0,0,0,.5),
             0 2px 4px rgba(0,0,0,.55);
  transition:transform 70ms ease,box-shadow 70ms ease,color 120ms ease;
}
.key:hover{color:var(--cream-100);}
.key:active{transform:translateY(1px);
  box-shadow:inset 0 2px 5px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,248,235,.05);}
.key.on{color:#ffd9b8;background:linear-gradient(180deg,#6b3d23,#3a2118);
  box-shadow:inset 0 1px 0 rgba(255,248,235,.18),inset 0 -2px 0 rgba(0,0,0,.5),
             0 0 14px rgba(197,96,44,.45),0 2px 4px rgba(0,0,0,.5);}

.controls{
  display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin-bottom:14px;
  padding:12px 14px;border-radius:12px;
  background:linear-gradient(180deg,var(--panel-700),var(--panel-800));
  box-shadow:inset 0 1px 0 rgba(255,248,235,.07),inset 0 0 0 1px rgba(0,0,0,.35),
             0 2px 8px rgba(0,0,0,.4);
}
input[type=search],input[type=number],select{
  font-family:Inter,sans-serif;font-size:.78rem;color:var(--cream-100);
  background:linear-gradient(180deg,#1d1b18,#211f1b);border:none;border-radius:8px;
  padding:9px 11px;
  box-shadow:inset 0 3px 8px rgba(0,0,0,.75),inset 0 0 0 1px rgba(0,0,0,.5),
             0 1px 0 rgba(255,248,235,.03);
}
input[type=search]{min-width:230px;flex:1 1 240px;}
input[type=number]{width:64px;flex:none;font-variant-numeric:tabular-nums;}
input[type=number]::-webkit-inner-spin-button{opacity:.5;}
select{cursor:pointer;max-width:180px;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;}
option{background:#211f1b;color:var(--cream-100);}
.ctl-label{font-family:"IBM Plex Mono",monospace;font-size:.56rem;font-weight:600;
  letter-spacing:.15em;text-transform:uppercase;color:var(--cream-500);}
.ctl-group{display:inline-flex;align-items:center;flex-wrap:wrap;gap:6px;
  max-width:100%;padding:3px 4px 3px 9px;border-radius:8px;background:rgba(0,0,0,.18);}
.ctl-group .ctl-label{padding-right:1px;}
.ctl-sep{width:1px;align-self:stretch;background:rgba(255,248,235,.06);margin:0 2px;}
#near-label{font-family:"IBM Plex Mono",monospace;font-size:.6rem;font-weight:600;
  color:var(--signal-glow);text-shadow:0 0 7px rgba(255,120,45,.4);
  white-space:nowrap;margin-left:2px;}
.tally{font-family:"IBM Plex Mono",monospace;font-size:.62rem;font-weight:600;
  letter-spacing:.1em;text-transform:uppercase;color:var(--signal-glow);
  text-shadow:0 0 7px rgba(255,120,45,.45);margin-left:auto;}
:focus-visible{outline:2px solid var(--signal-glow);outline-offset:2px;}

/* ── The well (data panel) ─────────────────────────────────────── */
.well{position:relative;border-radius:14px;overflow:hidden;
  background:linear-gradient(180deg,#1d1b18,#211f1b);
  box-shadow:inset 0 5px 13px rgba(0,0,0,.82),inset 0 2px 3px rgba(0,0,0,.7),
             inset 0 -2px 1px rgba(255,248,235,.03),0 1px 0 rgba(255,248,235,.03);}
.well-head{padding:11px 18px 10px;border-bottom:1px solid var(--edge-dark);
  box-shadow:0 1px 0 var(--edge-light);display:flex;align-items:center;
  justify-content:space-between;gap:14px;flex-wrap:wrap;}
.well-title{font-family:"IBM Plex Mono",monospace;font-size:.6rem;font-weight:600;
  letter-spacing:.14em;text-transform:uppercase;color:var(--cream-500);}
.well-count{font-family:"IBM Plex Mono",monospace;font-size:.6rem;font-weight:600;
  letter-spacing:.1em;text-transform:uppercase;color:var(--signal-glow);
  text-shadow:0 0 7px rgba(255,120,45,.5);}

/* ── Virtualised table ─────────────────────────────────────────── */
.scroller{height:min(66vh,780px);overflow:auto;overflow-x:auto;position:relative;}
table{border-collapse:collapse;width:100%;min-width:1180px;table-layout:fixed;}
thead th{
  position:sticky;top:0;z-index:5;text-align:left;
  background:linear-gradient(180deg,#2a2724,#232120);
  font-family:"IBM Plex Mono",monospace;font-size:.55rem;font-weight:600;
  letter-spacing:.15em;text-transform:uppercase;color:var(--cream-500);
  padding:9px 12px;border-bottom:1px solid rgba(0,0,0,.6);
  box-shadow:0 1px 0 var(--edge-light);white-space:nowrap;user-select:none;
}
thead th.sortable{cursor:pointer;}
thead th.sortable:hover{color:var(--cream-300);}
thead th .ind{color:var(--signal-glow);margin-left:4px;}
tbody tr{height:var(--row-h);}
tbody td{padding:0 12px;border-bottom:1px solid rgba(0,0,0,.42);
  box-shadow:inset 0 1px 0 rgba(255,248,235,.018);overflow:hidden;}
tbody tr.lead:hover td{background:rgba(255,248,235,.028);}
.addr{display:block;font-weight:700;color:var(--cream-100);font-size:.84rem;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.meta{display:block;font-family:"IBM Plex Mono",monospace;font-size:.58rem;
  letter-spacing:.07em;color:var(--cream-500);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;}
.meta a{color:var(--signal-glow);text-decoration:none;}
.meta a:hover{text-decoration:underline;}
.num{font-family:"IBM Plex Mono",monospace;font-size:.72rem;
  font-variant-numeric:tabular-nums;color:var(--cream-300);text-align:right;}
.score{font-family:"IBM Plex Mono",monospace;font-weight:600;font-size:.82rem;
  color:#ffbe85;text-align:right;font-variant-numeric:tabular-nums;
  text-shadow:0 0 10px rgba(232,118,52,.35);}
.val{font-weight:600;color:var(--cream-100);}
.pill{display:inline-block;font-family:"IBM Plex Mono",monospace;font-size:.55rem;
  font-weight:600;letter-spacing:.1em;padding:3px 7px;border-radius:3px;
  text-transform:uppercase;white-space:nowrap;}
.e78{background:rgba(208,80,80,.13);color:#e88b7a;border:1px solid rgba(208,80,80,.24);}
.e86{background:rgba(197,96,44,.13);color:var(--signal-glow);border:1px solid rgba(197,96,44,.24);}
.e91{background:rgba(197,140,44,.13);color:#dbb26a;border:1px solid rgba(197,140,44,.22);}
.e98{background:rgba(127,143,106,.15);color:#a8bb8a;border:1px solid rgba(127,143,106,.25);}
.e05{background:rgba(106,133,143,.15);color:#8fb2bd;border:1px solid rgba(106,133,143,.25);}
/* Pool condition. Green water and an original finish are the prospects, so they
   carry the signal colour; already-done and unconfirmable states stay muted. */
.c0{background:rgba(127,175,90,.16);color:#a8d47e;border:1px solid rgba(127,175,90,.3);}
.c1{background:rgba(197,96,44,.15);color:var(--signal-glow);border:1px solid rgba(197,96,44,.3);}
.c2{background:rgba(197,140,44,.12);color:#c9a765;border:1px solid rgba(197,140,44,.2);}
.c3{background:rgba(120,120,130,.12);color:#8b8b95;border:1px solid rgba(120,120,130,.2);}
.c4{background:rgba(120,120,130,.12);color:#8b8b95;border:1px solid rgba(120,120,130,.2);}
.c5{background:rgba(100,95,88,.12);color:var(--cream-500);border:1px solid rgba(100,95,88,.2);}
.c6{background:rgba(90,80,80,.12);color:#7a6f6f;border:1px solid rgba(90,80,80,.2);}
.ago{font-family:"IBM Plex Mono",monospace;font-size:.58rem;color:var(--cream-500);
  margin-left:6px;}
.tag{font-family:"IBM Plex Mono",monospace;font-size:.52rem;font-weight:600;
  color:var(--signal-glow);background:rgba(197,96,44,.12);
  border:1px solid rgba(197,96,44,.2);border-radius:3px;padding:1px 4px;margin-left:6px;}
.tag.ok{color:#7fc9a0;background:rgba(90,190,140,.11);border-color:rgba(90,190,140,.22);}
.tag.hold{color:#b9a58e;background:rgba(150,130,105,.11);border-color:rgba(150,130,105,.22);
  cursor:help;}
.approx{color:var(--cream-500);margin-left:5px;cursor:help;}

/* status key */
.st{font-family:Inter,sans-serif;font-size:.6rem;font-weight:700;letter-spacing:.09em;
  text-transform:uppercase;padding:6px 9px;border-radius:7px;cursor:pointer;border:none;
  min-width:104px;text-align:center;color:var(--cream-500);
  background:linear-gradient(180deg,var(--k-face-top),var(--k-face-bot));
  box-shadow:inset 0 1px 0 rgba(255,248,235,.12),inset 0 -2px 0 rgba(0,0,0,.45),
             0 1px 3px rgba(0,0,0,.5);
  transition:transform 60ms ease,box-shadow 60ms ease;}
.st:active{transform:translateY(1px);box-shadow:inset 0 2px 5px rgba(0,0,0,.6);}
tr[data-s="mailed"] .st{color:#ffd9b8;background:linear-gradient(180deg,#6b3d23,#3a2118);
  box-shadow:inset 0 1px 0 rgba(255,248,235,.15),0 0 12px rgba(197,96,44,.4);}
tr[data-s="replied"] .st{color:#bfe0ef;background:linear-gradient(180deg,#274a5a,#172c36);
  box-shadow:inset 0 1px 0 rgba(255,248,235,.13),0 0 12px rgba(60,140,180,.3);}
tr[data-s="quoted"] .st{color:#dcc9f2;background:linear-gradient(180deg,#4a3a68,#271d39);
  box-shadow:inset 0 1px 0 rgba(255,248,235,.13),0 0 12px rgba(120,90,190,.3);}
tr[data-s="won"] .st{color:#d3e8b8;background:linear-gradient(180deg,#41522f,#232c1a);
  box-shadow:inset 0 1px 0 rgba(255,248,235,.13),0 0 12px rgba(127,143,106,.45);}
tr[data-s="dead"] .st{color:var(--faint);background:linear-gradient(180deg,#2a2724,#201e1c);}
tr[data-s="dead"]{opacity:.42;}
tr[data-s="won"] .addr{color:#c3dba0;}

.note{font-family:Inter,sans-serif;font-size:.74rem;color:var(--cream-100);
  background:transparent;border:1px solid transparent;border-radius:6px;
  padding:6px 7px;width:100%;}
.note:hover{border-color:rgba(255,248,235,.09);}
.note:focus{background:rgba(0,0,0,.4);border-color:var(--signal-dim);outline:none;
  box-shadow:inset 0 2px 6px rgba(0,0,0,.6);}
.maplink{font-family:"IBM Plex Mono",monospace;font-size:.58rem;font-weight:600;
  letter-spacing:.1em;text-transform:uppercase;color:var(--cream-500);
  text-decoration:none;}
.maplink:hover{color:var(--signal-glow);}

.empty{padding:44px;text-align:center;color:var(--cream-500);font-size:.85rem;}
footer{margin-top:26px;font-family:"IBM Plex Mono",monospace;font-size:.6rem;
  line-height:2;color:var(--cream-500);letter-spacing:.05em;}
footer b{color:var(--cream-300);font-weight:600;}
footer a{color:var(--signal-glow);text-decoration:none;}
.legend{display:flex;flex-wrap:wrap;gap:13px;margin:0 0 22px;
  font-family:"IBM Plex Mono",monospace;font-size:.58rem;color:var(--cream-500);
  letter-spacing:.08em;align-items:center;}
.legend b{color:var(--cream-100);font-weight:600;}
@media (max-width:760px){
  :root{--pad:10px;}
  .shell{padding-bottom:60px;}
  .scroller{height:70vh;}
  .ctl-group{width:100%;}
  select{max-width:150px;}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important;}}
"""
