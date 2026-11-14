// ---- Mars solar model (shared by page and tests) ----
const MARS = { e:0.0934, obl:25.19*Math.PI/180, lsPeri:251*Math.PI/180, S0:1361/(1.5237*1.5237), year:668.6, solSec:88775, H:11.1 };
const D2R=Math.PI/180;
function orbit(sol){ // sol 0 = Ls 0 (northern spring equinox)
  const e=MARS.e, nu0=((0-MARS.lsPeri)%(2*Math.PI)+2*Math.PI)%(2*Math.PI);
  const E0=2*Math.atan2(Math.sqrt(1-e)*Math.sin(nu0/2),Math.sqrt(1+e)*Math.cos(nu0/2));
  const M=E0-e*Math.sin(E0)+2*Math.PI*sol/MARS.year;
  let E=M; for(let i=0;i<8;i++) E-= (E-e*Math.sin(E)-M)/(1-e*Math.cos(E));
  const nu=2*Math.atan2(Math.sqrt(1+e)*Math.sin(E/2),Math.sqrt(1-e)*Math.cos(E/2));
  let ls=(nu+MARS.lsPeri)%(2*Math.PI); if(ls<0) ls+=2*Math.PI;
  const flux=MARS.S0*Math.pow((1+e*Math.cos(nu))/(1-e*e),2);
  return {ls:ls/D2R, flux, decl:Math.asin(Math.sin(MARS.obl)*Math.sin(ls))};
}
// Dust: delta-Eddington two-stream total transmittance (Meador & Weaver 1980)
function transmit(mu,tau){
  if(tau<=0) return 1;
  let w=0.94,g=0.70; const f=g*g; tau=(1-w*f)*tau; const w2=(1-f)*w/(1-w*f); g=(g-f)/(1-f); w=w2;
  const g1=(7-w*(4+3*g))/4, g2=-(1-w*(4-3*g))/4, g3=(2-3*g*mu)/4, g4=1-g3;
  const k=Math.sqrt(g1*g1-g2*g2); if(Math.abs(1-k*mu)<1e-4) mu+=2e-4;
  const a1=g1*g4+g2*g3, ek=Math.exp(k*tau), em=Math.exp(-k*tau), et=Math.exp(-tau/mu);
  const D=(1-k*k*mu*mu)*((k+g1)*ek+(k-g1)*em);
  const T=et*(1-w/D*((1+k*mu)*(a1+k*g4)*ek-(1-k*mu)*(a1-k*g4)*em))+w/D*2*k*(g4+a1*mu);
  return Math.min(1,Math.max(0,T));
}
// Representative dust optical depth at the reference elevation (-1.4 km)
const SCEN={clear:{base:0.30,amp:0.30,storm:0},typical:{base:0.45,amp:0.45,storm:0},storm:{base:0.45,amp:0.45,storm:5}};
function tauRef(ls,sc){
  const s=SCEN[sc], b=(c,w)=>Math.exp(-0.5*Math.pow((ls-c)/w,2));
  let t=s.base+s.amp*Math.max(b(235,22),0.85*b(320,16),0.45*b(275,30));
  if(s.storm){ const d=ls-195; t+= d<0? s.storm*Math.exp(-0.5*(d/6)**2) : s.storm*Math.exp(-d/45); }
  return t;
}
function tauSite(ls,sc,elevKm){ return tauRef(ls,sc)*Math.exp(-(elevKm+1.4)/MARS.H); }
function pressure(elevKm){ return 610*Math.exp(-elevKm/MARS.H); }
// One sol at one site -> Wh/m2 on a flat surface, plus daylight hours (in 24.66 h sols)
function daily(latDeg,elevKm,sol,sc){
  const o=orbit(sol), phi=latDeg*D2R, tau=tauSite(o.ls,sc,elevKm);
  const x=-Math.tan(phi)*Math.tan(o.decl), h0= x>=1?0 : x<=-1?Math.PI : Math.acos(x);
  const N=48; let top=0,surf=0;
  for(let i=0;i<N;i++){ const h=(i+0.5)/N*h0, mu=Math.sin(phi)*Math.sin(o.decl)+Math.cos(phi)*Math.cos(o.decl)*Math.cos(h);
    if(mu>0){ top+=mu; surf+=mu*transmit(mu,tau);} }
  const k=o.flux*(2*h0/N)*MARS.solSec/(2*Math.PI)/3600;
  return {ls:o.ls,tau,top:top*k,surf:surf*k,dayHours:h0/Math.PI*MARS.solSec/3600};
}
function yearSeries(lat,elev,sc){ const a=[]; for(let s=0;s<669;s++) a.push(daily(lat,elev,s,sc)); return a; }
if(typeof module!=='undefined') module.exports={MARS,orbit,transmit,tauRef,tauSite,pressure,daily,yearSeries};
