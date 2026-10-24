/* Vignettes : illustrations originales d'un produit par catégorie (SVG, aucune image extérieure, aucun droit de tiers).
   Un décor (mur, sol, ombre) et l'objet, dans une palette tirée du produit : deux lits ne se ressemblent pas tout à fait.
   Proportions par catégorie (RATIO, hauteur / largeur) : une armoire est haute, un canapé est large, d'où la mosaïque. */

const WALLS = [["#F4EFE9", "#EAE2D8"], ["#EEF1EC", "#E1E6DF"], ["#F2ECEA", "#E7DED9"], ["#EDF0F3", "#DFE5EA"], ["#F5F0E6", "#EAE1D1"]];
const FLOORS = ["#DCCFBE", "#D2D7CE", "#DCCFC6", "#D0D7DD", "#DDCFB8"];
const FABRICS = [
  { b: "#D9CDBD", s: "#C3B4A0", l: "#E9E1D6" }, { b: "#B9C1AF", s: "#A0A995", l: "#D1D7C9" }, { b: "#CDB9A8", s: "#B59E8A", l: "#E0D2C5" },
  { b: "#AAB6C3", s: "#93A0AE", l: "#C7D0D9" }, { b: "#C99677", s: "#B07D5F", l: "#DDB296" }, { b: "#80838B", s: "#6A6D75", l: "#A0A3AA" }];
const WOODS = [{ b: "#B88E66", s: "#9B7552", l: "#CDA884" }, { b: "#8F6C51", s: "#775841", l: "#A8876B" }, { b: "#D6BA92", s: "#BEA078", l: "#E6D1B2" },
  { b: "#F3F1EC", s: "#DCD8D0", l: "#FFFFFF" }];
const STEEL = [{ b: "#F7F7F5", s: "#E1E2DF", l: "#FFFFFF", k: "#C4C8CC" }, { b: "#D9DCDF", s: "#C0C5C9", l: "#ECEEF0", k: "#A7ADB3" },
  { b: "#3B3E43", s: "#2C2F33", l: "#53575D", k: "#6E737A" }];
const ACCENTS = ["#7B5DC7", "#D9A93A", "#C9473B", "#4B7CC7", "#3E9A8D", "#D4704A"];

export const RATIO = {
  refrigerateur: 1.25, congelateur: 1.25, armoire: 1.25, aspirateur: 1.25,
  lit: 0.8, canape: 0.8, table: 0.8, buffet: 0.8, meuble_tv: 0.8, matelas: 0.8, sommier: 0.8, plaque_cuisson: 0.8,
};
export const ratioOf = cat => RATIO[cat] || 1;
const ZOOM = { 0.8: 1.16, 1: 1.14, 1.25: 1.04 };          // l'objet remplit la vignette, comme sur une photo de catalogue

const hash = s => { let h = 2166136261; for (const c of String(s)) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };
const pick = (arr, h, salt) => arr[(((h >>> salt) ^ Math.imul(h, salt + 7)) >>> 0) % arr.length];

/* ------------------------------------------------------------------ objets (repère : largeur 400, sol à y = F) */
const bed = (p, F) => <g>
  <rect x="62" y={F - 182} width="276" height="142" rx="18" fill={p.fab.b} />
  {[0, 1, 2, 3, 4].map(i => <rect key={i} x={84 + i * 50} y={F - 168} width="32" height="112" rx="10" fill={p.fab.l} opacity=".55" />)}
  <rect x="48" y={F - 76} width="304" height="56" rx="12" fill={p.fab.s} />
  <rect x="56" y={F - 92} width="288" height="34" rx="10" fill="#FBFAF7" />
  <rect x="52" y={F - 80} width="296" height="44" rx="12" fill={p.fab.l} />
  <path d={`M60 ${F - 58} Q200 ${F - 70} 340 ${F - 58}`} stroke={p.fab.s} strokeWidth="2" fill="none" opacity=".5" />
  <rect x="88" y={F - 118} width="100" height="36" rx="15" fill="#FFFFFF" />
  <rect x="212" y={F - 118} width="100" height="36" rx="15" fill="#FFFFFF" />
  <rect x="168" y={F - 108} width="64" height="28" rx="12" fill={p.accent} opacity=".85" />
  <rect x="66" y={F - 22} width="9" height="22" rx="2" fill={p.wood.s} /><rect x="325" y={F - 22} width="9" height="22" rx="2" fill={p.wood.s} />
</g>;

const sofa = (p, F) => <g>
  <rect x="50" y={F - 150} width="300" height="96" rx="24" fill={p.fab.b} />
  {[0, 1, 2].map(i => <rect key={i} x={74 + i * 86} y={F - 140} width="80" height="74" rx="18" fill={p.fab.l} />)}
  <rect x="62" y={F - 76} width="276" height="44" rx="14" fill={p.fab.l} />
  <path d={`M154 ${F - 74} V${F - 34} M246 ${F - 74} V${F - 34}`} stroke={p.fab.s} strokeWidth="2" opacity=".6" />
  <rect x="34" y={F - 106} width="46" height="84" rx="20" fill={p.fab.b} /><rect x="320" y={F - 106} width="46" height="84" rx="20" fill={p.fab.b} />
  <rect x="44" y={F - 36} width="312" height="16" rx="7" fill={p.fab.s} />
  <rect x="96" y={F - 118} width="54" height="44" rx="12" fill={p.accent} opacity=".85" transform={`rotate(-8 123 ${F - 96})`} />
  <path d={`M64 ${F - 20} L58 ${F}`} stroke={p.wood.s} strokeWidth="7" strokeLinecap="round" />
  <path d={`M336 ${F - 20} L342 ${F}`} stroke={p.wood.s} strokeWidth="7" strokeLinecap="round" />
</g>;

const armchair = (p, F) => <g>
  <rect x="118" y={F - 214} width="164" height="156" rx="44" fill={p.fab.b} />
  <rect x="134" y={F - 198} width="132" height="112" rx="34" fill={p.fab.l} opacity=".6" />
  <rect x="104" y={F - 92} width="192" height="48" rx="18" fill={p.fab.l} />
  <rect x="84" y={F - 128} width="46" height="98" rx="22" fill={p.fab.b} /><rect x="270" y={F - 128} width="46" height="98" rx="22" fill={p.fab.b} />
  <rect x="92" y={F - 44} width="216" height="14" rx="6" fill={p.fab.s} />
  <path d={`M110 ${F - 30} L102 ${F}`} stroke={p.wood.s} strokeWidth="8" strokeLinecap="round" />
  <path d={`M290 ${F - 30} L298 ${F}`} stroke={p.wood.s} strokeWidth="8" strokeLinecap="round" />
  <rect x="176" y={F - 150} width="48" height="40" rx="12" fill={p.accent} opacity=".85" />
</g>;

const table = (p, F) => <g>
  <path d={`M108 ${F - 92} L102 ${F - 8} M292 ${F - 92} L298 ${F - 8}`} stroke={p.wood.s} strokeWidth="9" strokeLinecap="round" opacity=".55" />
  <rect x="52" y={F - 104} width="296" height="15" rx="5" fill={p.wood.b} />
  <rect x="58" y={F - 90} width="284" height="7" rx="3" fill={p.wood.s} />
  <path d={`M86 ${F - 84} L78 ${F} M314 ${F - 84} L322 ${F}`} stroke={p.wood.s} strokeWidth="11" strokeLinecap="round" />
  <path d={`M188 ${F - 104} Q186 ${F - 140} 196 ${F - 140} H204 Q214 ${F - 140} 212 ${F - 104} Z`} fill="#F1ECE4" />
  <path d={`M200 ${F - 140} C190 ${F - 180} 168 ${F - 186} 160 ${F - 200} M200 ${F - 140} C206 ${F - 186} 226 ${F - 194} 238 ${F - 212} M200 ${F - 140} C200 ${F - 176} 200 ${F - 196} 204 ${F - 222}`}
    stroke="#8DA287" strokeWidth="4" fill="none" strokeLinecap="round" />
  <ellipse cx="166" cy={F - 196} rx="12" ry="6" fill="#9AB094" transform={`rotate(-30 166 ${F - 196})`} />
  <ellipse cx="232" cy={F - 206} rx="13" ry="6" fill="#9AB094" transform={`rotate(-40 232 ${F - 206})`} />
  <ellipse cx="204" cy={F - 218} rx="6" ry="12" fill="#A4B99E" />
</g>;

const wardrobe = (p, F) => <g>
  <rect x="96" y={F - 360} width="208" height="344" rx="10" fill={p.wood.b} />
  <rect x="106" y={F - 350} width="91" height="324" rx="6" fill={p.wood.l} opacity=".55" />
  <rect x="203" y={F - 350} width="91" height="324" rx="6" fill={p.wood.l} opacity=".55" />
  <rect x="186" y={F - 214} width="5" height="46" rx="2.5" fill={p.wood.s} /><rect x="209" y={F - 214} width="5" height="46" rx="2.5" fill={p.wood.s} />
  <rect x="104" y={F - 18} width="192" height="10" rx="3" fill={p.wood.s} />
  <rect x="112" y={F - 10} width="8" height="10" fill={p.wood.s} /><rect x="280" y={F - 10} width="8" height="10" fill={p.wood.s} />
</g>;

const dresser = (p, F) => <g>
  <rect x="98" y={F - 168} width="204" height="148" rx="8" fill={p.wood.b} />
  {[0, 1, 2].map(i => <g key={i}><rect x="108" y={F - 160 + i * 46} width="184" height="40" rx="5" fill={p.wood.l} opacity=".6" />
    <circle cx="200" cy={F - 140 + i * 46} r="4" fill={p.wood.s} /></g>)}
  <path d={`M112 ${F - 20} L106 ${F} M288 ${F - 20} L294 ${F}`} stroke={p.wood.s} strokeWidth="7" strokeLinecap="round" />
  <rect x="226" y={F - 196} width="10" height="28" fill={p.steel.k} />
  <path d={`M206 ${F - 238} H256 L266 ${F - 196} H196 Z`} fill="#FBF7EF" />
  <rect x="122" y={F - 190} width="40" height="22" rx="3" fill={p.accent} opacity=".8" /><rect x="128" y={F - 204} width="34" height="14" rx="3" fill={p.fab.b} />
</g>;

const sideboard = (p, F) => <g>
  <rect x="44" y={F - 128} width="312" height="98" rx="8" fill={p.wood.b} />
  {[0, 1, 2].map(i => <g key={i}><rect x={54 + i * 100} y={F - 120} width="92" height="82" rx="5" fill={p.wood.l} opacity=".5" />
    {[0, 1, 2, 3, 4, 5].map(j => <path key={j} d={`M${66 + i * 100 + j * 14} ${F - 114} V${F - 44}`} stroke={p.wood.s} strokeWidth="2" opacity=".35" />)}</g>)}
  <path d={`M60 ${F - 30} L52 ${F} M340 ${F - 30} L348 ${F}`} stroke={p.wood.s} strokeWidth="8" strokeLinecap="round" />
  <path d={`M238 ${F - 128} Q236 ${F - 160} 246 ${F - 162} H256 Q266 ${F - 160} 264 ${F - 128} Z`} fill="#F1ECE4" />
  <path d={`M251 ${F - 162} C246 ${F - 190} 232 ${F - 196} 224 ${F - 206} M251 ${F - 162} C256 ${F - 192} 270 ${F - 198} 280 ${F - 210}`} stroke="#8DA287" strokeWidth="4" fill="none" strokeLinecap="round" />
  <rect x="96" y={F - 150} width="56" height="22" rx="3" fill={p.accent} opacity=".8" />
</g>;

const tvstand = (p, F) => <g>
  <rect x="56" y={F - 78} width="288" height="54" rx="8" fill={p.wood.b} />
  <rect x="66" y={F - 70} width="128" height="38" rx="5" fill={p.wood.l} opacity=".5" /><rect x="206" y={F - 70} width="128" height="38" rx="5" fill={p.wood.l} opacity=".5" />
  <path d={`M72 ${F - 24} L66 ${F} M328 ${F - 24} L334 ${F}`} stroke={p.wood.s} strokeWidth="7" strokeLinecap="round" />
  <rect x="190" y={F - 92} width="20" height="14" fill="#2A2D31" />
  <rect x="106" y={F - 196} width="188" height="106" rx="6" fill="#23262A" />
  <rect x="113" y={F - 189} width="174" height="92" rx="3" fill="#30353B" />
  <path d={`M113 ${F - 189} H210 L150 ${F - 97} H113 Z`} fill="#FFFFFF" opacity=".06" />
</g>;

const mattress = (p, F) => <g>
  <path d={`M58 ${F - 110} L292 ${F - 128} L348 ${F - 92} L112 ${F - 72} Z`} fill="#FBFAF7" />
  <path d={`M112 ${F - 72} L348 ${F - 92} L348 ${F - 40} L112 ${F - 20} Z`} fill={p.fab.l} />
  <path d={`M58 ${F - 110} L112 ${F - 72} L112 ${F - 20} L58 ${F - 56} Z`} fill={p.fab.s} />
  <path d={`M112 ${F - 50} L348 ${F - 70}`} stroke={p.fab.b} strokeWidth="6" />
  {[0, 1, 2, 3].map(i => [0, 1, 2, 3, 4, 5].map(j => <circle key={`${i}${j}`} cx={96 + j * 40 + i * 12} cy={F - 112 + i * 9 - j * 3} r="2.2" fill={p.fab.s} opacity=".6" />))}
</g>;

const bedbase = (p, F) => <g>
  <path d={`M58 ${F - 92} L292 ${F - 108} L348 ${F - 76} L112 ${F - 58} Z`} fill={p.fab.l} />
  {[0, 1, 2, 3, 4, 5, 6].map(i => <path key={i} d={`M${72 + i * 34} ${F - 92 + i * -2.2} L${120 + i * 34} ${F - 60 - i * 2.4}`} stroke={p.fab.s} strokeWidth="5" opacity=".45" />)}
  <path d={`M112 ${F - 58} L348 ${F - 76} L348 ${F - 52} L112 ${F - 34} Z`} fill={p.fab.b} />
  <path d={`M58 ${F - 92} L112 ${F - 58} L112 ${F - 34} L58 ${F - 66} Z`} fill={p.fab.s} />
  <rect x="118" y={F - 36} width="9" height="34" rx="2" fill={p.wood.s} /><rect x="334" y={F - 54} width="9" height="40" rx="2" fill={p.wood.s} />
  <rect x="64" y={F - 68} width="8" height="30" rx="2" fill={p.wood.s} opacity=".7" />
</g>;

const fridge = (p, F) => <g>
  <rect x="118" y={F - 372} width="164" height="356" rx="16" fill={p.steel.b} />
  <rect x="268" y={F - 366} width="12" height="344" rx="6" fill={p.steel.s} />
  <path d={`M120 ${F - 132} H280`} stroke={p.steel.k} strokeWidth="3" />
  <rect x="250" y={F - 318} width="7" height="96" rx="3.5" fill={p.steel.k} /><rect x="250" y={F - 118} width="7" height="58" rx="3.5" fill={p.steel.k} />
  <rect x="136" y={F - 350} width="40" height="14" rx="4" fill={p.steel.s} />
  <rect x="124" y={F - 16} width="152" height="10" rx="3" fill={p.steel.s} />
</g>;

const freezer = (p, F) => <g>
  <rect x="122" y={F - 372} width="156" height="356" rx="14" fill={p.steel.b} />
  <rect x="264" y={F - 366} width="12" height="344" rx="6" fill={p.steel.s} />
  {[1, 2, 3].map(i => <path key={i} d={`M124 ${F - 372 + i * 89} H276`} stroke={p.steel.k} strokeWidth="3" />)}
  {[0, 1, 2, 3].map(i => <rect key={i} x="166" y={F - 362 + i * 89} width="68" height="7" rx="3.5" fill={p.steel.k} />)}
  <rect x="128" y={F - 16} width="144" height="10" rx="3" fill={p.steel.s} />
</g>;

const washer = (p, F, dryer) => <g>
  <rect x="104" y={F - 236} width="192" height="226" rx="14" fill={p.steel.b} />
  <rect x="104" y={F - 236} width="192" height="40" rx="14" fill={p.steel.l} />
  <path d={`M104 ${F - 196} H296`} stroke={p.steel.k} strokeWidth="2" />
  <rect x="120" y={F - 224} width="54" height="16" rx="4" fill={p.steel.s} />
  <circle cx="262" cy={F - 216} r="11" fill={p.steel.s} /><circle cx="262" cy={F - 216} r="5" fill={p.steel.k} />
  {dryer && <circle cx="232" cy={F - 216} r="7" fill={p.steel.s} />}
  <circle cx="200" cy={F - 106} r="66" fill={p.steel.s} />
  <circle cx="200" cy={F - 106} r="52" fill={dryer ? "#59636B" : "#2C3136"} />
  <circle cx="200" cy={F - 106} r="38" fill={dryer ? "#6B757D" : "#3A4249"} />
  <path d={`M166 ${F - 132} A44 44 0 0 1 224 ${F - 146}`} stroke="#FFFFFF" strokeWidth="5" strokeLinecap="round" fill="none" opacity=".35" />
  <rect x="112" y={F - 22} width="176" height="8" rx="3" fill={p.steel.s} />
</g>;

const dishwasher = (p, F) => <g>
  <rect x="104" y={F - 236} width="192" height="226" rx="12" fill={p.steel.b} />
  <rect x="104" y={F - 236} width="192" height="30" rx="12" fill={p.steel.s} />
  {[0, 1, 2, 3].map(i => <circle key={i} cx={128 + i * 18} cy={F - 221} r="4" fill={p.steel.k} />)}
  <rect x="236" y={F - 227} width="44" height="12" rx="3" fill="#2C3136" />
  <rect x="130" y={F - 192} width="140" height="9" rx="4.5" fill={p.steel.k} />
  <rect x="104" y={F - 34} width="192" height="24" rx="6" fill={p.steel.s} />
</g>;

const oven = (p, F) => <g>
  <rect x="78" y={F - 262} width="244" height="252" rx="6" fill={p.wood.b} />
  <rect x="104" y={F - 236} width="192" height="196" rx="8" fill="#2E3236" />
  <rect x="104" y={F - 236} width="192" height="32" rx="8" fill="#3C4147" />
  <circle cx="128" cy={F - 220} r="8" fill="#5A6067" /><circle cx="272" cy={F - 220} r="8" fill="#5A6067" />
  <rect x="172" y={F - 228} width="56" height="16" rx="3" fill="#1B1E21" /><rect x="180" y={F - 223} width="20" height="6" rx="1" fill="#E9A23B" opacity=".9" />
  <rect x="124" y={F - 196} width="152" height="8" rx="4" fill="#A5ABB1" />
  <rect x="124" y={F - 178} width="152" height="118" rx="8" fill="#1B1E21" />
  <path d={`M124 ${F - 178} H214 L164 ${F - 60} H124 Z`} fill="#FFFFFF" opacity=".06" />
  <rect x="138" y={F - 96} width="124" height="4" rx="2" fill="#E9A23B" opacity=".25" />
</g>;

const hob = (p, F) => <g>
  <path d={`M30 ${F - 100} L370 ${F - 112} L392 ${F - 40} L8 ${F - 26} Z`} fill={p.wood.l} />
  <path d={`M8 ${F - 26} L392 ${F - 40} L392 ${F - 28} L8 ${F - 14} Z`} fill={p.wood.s} />
  <path d={`M104 ${F - 96} L298 ${F - 103} L318 ${F - 44} L82 ${F - 36} Z`} fill="#25282C" />
  {[[150, F - 84, 30, 9], [250, F - 88, 24, 7], [142, F - 56, 24, 7], [256, F - 60, 32, 10]].map(([x, y, rx, ry], i) =>
    <ellipse key={i} cx={x} cy={y} rx={rx} ry={ry} fill="none" stroke="#6C737A" strokeWidth="2.5" />)}
  <path d={`M180 ${F - 42} H222`} stroke="#E9A23B" strokeWidth="3" strokeLinecap="round" opacity=".7" />
</g>;

const hood = (p, F) => <g>
  <rect x="178" y={F - 330} width="44" height="150" fill={p.steel.b} />
  <rect x="210" y={F - 330} width="12" height="150" fill={p.steel.s} />
  <path d={`M112 ${F - 112} H288 L252 ${F - 182} H148 Z`} fill={p.steel.b} />
  <path d={`M252 ${F - 182} L288 ${F - 112} H270 L240 ${F - 182} Z`} fill={p.steel.s} />
  <rect x="106" y={F - 114} width="188" height="18" rx="3" fill={p.steel.s} />
  <rect x="150" y={F - 98} width="100" height="4" rx="2" fill="#FFF3D6" />
  <path d={`M150 ${F - 94} L120 ${F - 20} H280 L250 ${F - 94} Z`} fill="#FFF3D6" opacity=".25" />
</g>;

const stickvac = (p, F) => <g>
  <path d={`M236 ${F - 392} L176 ${F - 34}`} stroke={p.steel.k} strokeWidth="9" strokeLinecap="round" />
  <path d={`M222 ${F - 404} Q248 ${F - 420} 262 ${F - 396} L250 ${F - 360}`} stroke="#2E3136" strokeWidth="12" strokeLinecap="round" fill="none" />
  <rect x="214" y={F - 356} width="50" height="128" rx="22" fill={p.accent} transform={`rotate(10 239 ${F - 292})`} />
  <rect x="222" y={F - 300} width="34" height="62" rx="14" fill="#E6EAEE" opacity=".9" transform={`rotate(10 239 ${F - 270})`} />
  <rect x="122" y={F - 40} width="118" height="30" rx="13" fill="#2E3136" />
  <rect x="134" y={F - 34} width="70" height="8" rx="4" fill={p.accent} opacity=".9" />
</g>;

const robotvac = (p, F) => <g>
  <path d={`M76 ${F - 58} A124 40 0 0 0 324 ${F - 58} V${F - 34} A124 40 0 0 1 76 ${F - 34} Z`} fill={p.steel.s} />
  <ellipse cx="200" cy={F - 58} rx="124" ry="40" fill={p.steel.b} />
  <ellipse cx="200" cy={F - 60} rx="96" ry="28" fill="none" stroke={p.steel.k} strokeWidth="2" opacity=".5" />
  <path d={`M180 ${F - 76} A26 9 0 0 0 232 ${F - 76} V${F - 66} A26 9 0 0 1 180 ${F - 66} Z`} fill={p.steel.k} />
  <ellipse cx="206" cy={F - 76} rx="26" ry="9" fill={p.steel.l} />
  <path d={`M112 ${F - 38} A110 30 0 0 0 288 ${F - 38}`} stroke={p.accent} strokeWidth="4" fill="none" opacity=".8" />
</g>;

const parcel = (p, F) => <g>
  <path d={`M120 ${F - 170} L200 ${F - 200} L280 ${F - 170} L200 ${F - 140} Z`} fill={p.wood.l} />
  <path d={`M120 ${F - 170} L200 ${F - 140} V${F - 20} L120 ${F - 50} Z`} fill={p.wood.b} />
  <path d={`M280 ${F - 170} L200 ${F - 140} V${F - 20} L280 ${F - 50} Z`} fill={p.wood.s} />
</g>;

const DRAW = {
  lit: bed, canape: sofa, fauteuil: armchair, table, armoire: wardrobe, commode: dresser, buffet: sideboard, meuble_tv: tvstand,
  matelas: mattress, sommier: bedbase, refrigerateur: fridge, congelateur: freezer, lave_linge: (p, F) => washer(p, F, false),
  lave_linge_sechant: (p, F) => washer(p, F, false), seche_linge: (p, F) => washer(p, F, true), lave_vaisselle: dishwasher,
  four: oven, cuisiniere: oven, micro_ondes: oven, plaque_cuisson: hob, hotte: hood, aspirateur: stickvac, robot_aspirateur: robotvac,
};

/* Une vignette : décor + objet. seed = identifiant du produit (couleurs stables d'un jour à l'autre). ratio, floor et
   zoom recadrent la scène (carte de pièce, plus haute que l'objet : le sol monte, l'objet entier reste visible). */
export function Vignette({ category, seed = 0, label, ratio, floor, zoom }) {
  const H = Math.round(400 * (ratio || ratioOf(category))), F = floor ? Math.round(H * floor) : H - 54, h = hash(seed);
  const p = { fab: pick(FABRICS, h, 1), wood: pick(WOODS, h, 3), steel: pick(STEEL, h, 5), accent: pick(ACCENTS, h, 7) };
  const wall = pick(WALLS, h, 9), ground = FLOORS[WALLS.indexOf(wall)];
  const id = `v${h.toString(36)}${category || ""}`;
  return <svg viewBox={`0 0 400 ${H}`} width="100%" height="100%" preserveAspectRatio="xMidYMid slice" role="img" aria-label={label}
    style={{ display: "block" }}>
    <defs>
      <linearGradient id={`${id}w`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={wall[0]} /><stop offset="1" stopColor={wall[1]} /></linearGradient>
      <radialGradient id={`${id}s`}><stop offset="0" stopColor="#5A4632" stopOpacity=".22" /><stop offset="1" stopColor="#5A4632" stopOpacity="0" /></radialGradient>
    </defs>
    <rect width="400" height={F} fill={`url(#${id}w)`} />
    <rect y={F} width="400" height={H - F} fill={ground} />
    <rect y={F} width="400" height="3" fill="#FFFFFF" opacity=".35" />
    <ellipse cx="200" cy={F + 2} rx="170" ry="16" fill={`url(#${id}s)`} />
    <g transform={`translate(200 ${F}) scale(${zoom || ZOOM[ratioOf(category)] || 1.1}) translate(-200 ${-F})`}>{(DRAW[category] || parcel)(p, F)}</g>
  </svg>;
}
