/* Candidate values stay in memory; only counts leave collect(). No media permission. */
async function collect(url, duration = 7000, Peer = globalThis.RTCPeerConnection) {
  const result = {server:url, status:'inconclusive', gathering_complete:false,
    candidates:0, mdns:0, literal_ipv4:0, literal_ipv6:0, srflx:0, relay:0};
  if (typeof Peer !== 'function') return {...result,status:'api-unavailable'};
  let pc, timer, finish, expired = false, closed = false;
  const deadline = new Promise(resolve => {
    finish=resolve;
    timer=setTimeout(() => { expired=true; resolve(); },duration);
  });
  try {
    pc = new Peer({iceServers:[{urls:url}]});
    pc.onicecandidate = event => {
      if (closed || !event.candidate) return;
      const c=event.candidate;
      const address=c.address || c.candidate.split(' ')[4] || '';
      const type=c.type || c.candidate.split(' typ ')[1]?.split(' ')[0];
      result.candidates++;
      if (address.endsWith('.local')) result.mdns++;
      else if (/^\d+\.\d+\.\d+\.\d+$/.test(address)) result.literal_ipv4++;
      else if (address.includes(':')) result.literal_ipv6++;
      if (type==='srflx') result.srflx++;
      if (type==='relay') result.relay++;
    };
    pc.onicegatheringstatechange = () => {
      if (!closed && pc.iceGatheringState==='complete') {
        result.gathering_complete=true; finish();
      }
    };
    pc.createDataChannel('local-audit');
    const negotiation=pc.createOffer().then(offer => {
      if (!expired && !closed) return pc.setLocalDescription(offer);
    });
    await Promise.race([negotiation,deadline]);
    if (!expired) await deadline;
    result.status=result.gathering_complete?'gathering-complete':'inconclusive';
  } catch (error) {
    result.status='error'; result.error=error.name;
  } finally {
    closed=true;
    clearTimeout(timer);
    if (pc) { pc.onicecandidate=null; pc.onicegatheringstatechange=null; pc.close(); }
  }
  return result;
}
if (typeof document !== 'undefined') {
  document.querySelector('#start').onclick=async()=>{
    const button=document.querySelector('#start'), output=document.querySelector('#result');
    button.disabled=true; output.textContent='正在检查…';
    try {
      const result={started_utc:new Date().toISOString(),tests:[]};
      for (const url of ['stun:stun.l.google.com:19302','stun:stun.cloudflare.com:3478']) {
        result.tests.push(await collect(url));
      }
      result.completed_utc=new Date().toISOString();
      output.textContent=JSON.stringify(result,null,2);
    } finally { button.disabled=false; }
  };
}
if (typeof module !== 'undefined') module.exports={collect};
