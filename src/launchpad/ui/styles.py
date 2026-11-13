"""Global CSS. Look: a paper-and-ink 'dispatch desk' - warm paper, serif headlines, hard offset shadows, mono labels."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=IBM+Plex+Mono:wght@400;500&family=Instrument+Sans:wght@400;500;600&display=swap');
:root{
  --paper:#F5EFE3; --card:#FFFCF4; --ink:#1F2A24; --muted:#6B6A5E; --rule:#D8CCB2;
  --market:#3F6B4F; --creative:#B4532A; --final:#2F4B6B; --flow:#9A7410;
  --pass:#3F6B4F; --retry:#B7791F; --bad:#A63D2F; --info:#2F4B6B; --violet:#6B4E8C;
}
html, body, .stApp, [data-testid="stAppViewContainer"]{background:var(--paper)!important;}
.stApp, .stApp p, .stApp li, .stApp label, .stApp span{font-family:'Instrument Sans',system-ui,sans-serif;}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"]{display:none!important;}
header[data-testid="stHeader"]{background:transparent!important;}
.block-container{padding-top:1.6rem!important;max-width:1280px;}
[data-testid="stSidebar"]{background:#EBE2D0!important;border-right:1px solid var(--rule);}
[data-testid="stSidebar"] *{color:var(--ink);}
.stButton>button{border:1px solid var(--ink)!important;background:var(--card)!important;color:var(--ink)!important;border-radius:2px!important;
  box-shadow:2px 2px 0 var(--ink);font-weight:500;transition:transform .08s, box-shadow .08s;}
.stButton>button:hover{transform:translate(1px,1px);box-shadow:1px 1px 0 var(--ink);background:#FFF3C4!important;}
[data-testid="stChatInput"]{background:var(--card)!important;border:1px solid var(--ink)!important;border-radius:2px!important;box-shadow:3px 3px 0 var(--ink);}
[data-testid="stChatInput"] textarea{font-family:'Instrument Sans',sans-serif!important;color:var(--ink)!important;}
[data-testid="stBottom"], [data-testid="stBottomBlockContainer"]{background:var(--paper)!important;}
button[data-baseweb="tab"]{font-family:'IBM Plex Mono',monospace!important;font-size:12px!important;letter-spacing:.04em;text-transform:uppercase;}
[data-testid="stDownloadButton"] button{font-size:13px;}

.mast{display:flex;align-items:flex-end;justify-content:space-between;border-bottom:3px double var(--ink);padding-bottom:.55rem;margin-bottom:1.1rem;}
.mast h1{font-family:'Fraunces',Georgia,serif;font-weight:700;font-size:2.5rem;line-height:1;margin:0;letter-spacing:-.02em;color:var(--ink);}
.mast h1 i{font-style:italic;font-weight:400;color:var(--creative);}
.mast .sub{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);text-align:right;line-height:1.6;}

.note-user{display:flex;justify-content:flex-end;margin:1rem 0 .6rem;}
.note-user .sticky{background:#FFF0B8;border:1px solid #E3CE7E;padding:.7rem .95rem;max-width:78%;font-family:'Fraunces',serif;font-size:1.02rem;
  line-height:1.4;box-shadow:3px 3px 0 #E3CE7E;transform:rotate(-.35deg);color:var(--ink);}
.note-user .who{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:#8a7424;display:block;margin-bottom:.25rem;}

.memo{background:var(--card);border:1px solid var(--rule);border-left:6px solid var(--c,var(--ink));box-shadow:3px 3px 0 var(--rule);
  padding:.7rem .95rem .75rem;margin:.55rem 0;border-radius:2px;color:var(--ink);}
.memo .hd{display:flex;align-items:center;gap:.55rem;margin-bottom:.35rem;flex-wrap:wrap;}
.tag{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;padding:2px 7px;border-radius:2px;
  background:color-mix(in srgb,var(--c,var(--ink)) 13%,transparent);color:var(--c,var(--ink));font-weight:500;}
.memo .role{font-weight:600;font-size:.95rem;}
.memo .what{color:var(--muted);font-size:.85rem;}
.memo .ts{margin-left:auto;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);}
.memo .sum{font-size:.94rem;line-height:1.5;}
.memo details{margin-top:.4rem;}
.memo summary{cursor:pointer;font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);}
.memo pre{white-space:pre-wrap;word-break:break-word;font-family:'IBM Plex Mono',monospace;font-size:12px;line-height:1.55;background:#F7F1E2;padding:.6rem;margin:.4rem 0 0;border:1px dashed var(--rule);}

.line{font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:var(--muted);display:flex;gap:.6rem;align-items:center;margin:.45rem 0;}
.line:before,.line:after{content:"";height:1px;background:var(--rule);flex:1;}
.line b{color:var(--ink);font-weight:500;}
.alert{font-size:.86rem;border:1px dashed var(--c);color:var(--ink);background:color-mix(in srgb,var(--c) 7%,var(--card));padding:.4rem .7rem;margin:.4rem 0 .4rem 1.4rem;border-radius:2px;}
.alert .k{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--c);margin-right:.4rem;}
.typing{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--muted);margin:.6rem 0 .2rem 1.4rem;}
.typing .dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--creative);margin-right:3px;animation:blink 1.1s infinite;}
.typing .dot:nth-child(2){animation-delay:.18s}.typing .dot:nth-child(3){animation-delay:.36s}
@keyframes blink{0%,80%,100%{opacity:.15}40%{opacity:1}}

.welcome{background:var(--card);border:1px solid var(--ink);box-shadow:5px 5px 0 var(--ink);padding:1.4rem 1.6rem;margin-top:.4rem;}
.welcome h3{font-family:'Fraunces',serif;font-size:1.5rem;margin:0 0 .4rem;color:var(--ink);}
.welcome p{margin:.3rem 0;line-height:1.55;color:var(--ink);}
.welcome .steps{display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem;margin-top:1rem;}
.welcome .step{border-top:3px solid var(--c);padding-top:.45rem;font-size:.88rem;line-height:1.45;color:var(--ink);}
.welcome .step b{display:block;font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--c);margin-bottom:.15rem;}

.doc{background:var(--card);border:1px solid var(--ink);box-shadow:5px 5px 0 var(--ink);padding:1.3rem 1.5rem 1.4rem;margin:1rem 0 .6rem;color:var(--ink);}
.doc .top{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;border-bottom:1px solid var(--rule);padding-bottom:.7rem;margin-bottom:.9rem;}
.doc h2{font-family:'Fraunces',serif;font-size:1.7rem;margin:0;line-height:1.1;color:var(--ink);}
.doc .eyebrow{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);}
.stamp{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;text-transform:uppercase;border:2px solid var(--c);color:var(--c);
  padding:.25rem .55rem;transform:rotate(3deg);white-space:nowrap;font-weight:500;}
.doc h4{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:1.1rem 0 .3rem;font-weight:500;}
.doc p,.doc li{font-size:.97rem;line-height:1.55;color:var(--ink);}
.doc ul,.doc ol{margin:.2rem 0 0 1.1rem;padding:0;}
.doc blockquote{font-family:'Fraunces',serif;font-size:1.1rem;font-style:italic;border-left:4px solid var(--creative);margin:.2rem 0;padding:.1rem .9rem;}
.chip{display:inline-block;border:1px solid var(--ink);padding:.18rem .6rem;margin:0 .35rem .35rem 0;font-family:'Fraunces',serif;font-size:.98rem;background:#FFF3C4;}
.chip.plain{background:transparent;font-family:'Instrument Sans',sans-serif;font-size:.88rem;}
.doc table{width:100%;border-collapse:collapse;font-size:.92rem;margin-top:.2rem;}
.doc th{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;text-align:left;color:var(--muted);border-bottom:2px solid var(--ink);padding:.3rem .4rem;}
.doc td{border-bottom:1px solid var(--rule);padding:.4rem;vertical-align:top;color:var(--ink);}
.doc .cta{margin-top:1.1rem;background:var(--ink);color:#FFF9E6;padding:.75rem 1rem;font-family:'Fraunces',serif;font-size:1.05rem;}

.panel{background:var(--card);border:1px solid var(--rule);box-shadow:3px 3px 0 var(--rule);padding:.8rem .9rem;margin-bottom:.9rem;color:var(--ink);}
.panel h5{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:0 0 .55rem;font-weight:500;display:flex;justify-content:space-between;align-items:center;}
.par{font-size:10px;letter-spacing:.1em;background:var(--creative);color:#fff;padding:1px 6px;border-radius:2px;}
.lane{border-left:4px solid var(--c);padding:.1rem 0 .1rem .65rem;margin:.55rem 0;}
.lane .t{font-weight:600;font-size:.9rem;display:flex;justify-content:space-between;gap:.5rem;}
.lane .p{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--c);font-weight:400;}
.tk{font-size:.84rem;margin:.18rem 0;display:flex;gap:.5rem;align-items:center;color:var(--ink);}
.dot-s{width:9px;height:9px;border-radius:50%;border:1.5px solid var(--muted);flex:none;}
.st-run .dot-s{background:var(--creative);border-color:var(--creative);animation:blink 1s infinite;}
.st-done .dot-s{background:var(--pass);border-color:var(--pass);}
.st-skip .dot-s{border-style:dashed;}
.st-fail .dot-s{background:var(--bad);border-color:var(--bad);}
.st-skip,.st-wait{color:var(--muted);}
.led{font-family:'IBM Plex Mono',monospace;font-size:11.5px;line-height:1.45;padding:.32rem 0;border-bottom:1px dotted var(--rule);color:var(--ink);}
.led .v{display:inline-block;min-width:54px;text-align:center;padding:0 5px;margin-right:.4rem;border-radius:2px;font-size:10px;letter-spacing:.08em;text-transform:uppercase;
  color:#fff;background:var(--c,var(--muted));}
.led .d{color:var(--muted);display:block;margin-left:.1rem;}
.led .tm{float:right;color:var(--muted);}
.legend{font-size:11px;color:var(--muted);margin-bottom:.4rem;font-family:'IBM Plex Mono',monospace;}
.empty{font-size:.85rem;color:var(--muted);font-style:italic;}
</style>
"""
