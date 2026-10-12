const {test}=require('node:test');
const assert=require('node:assert/strict');
const {collect}=require('../assets/webrtc-probe.js');
const url='stun:synthetic.invalid:3478';
let closed=0, descriptions=0;
class Peer {
  createDataChannel() {}
  async createOffer() { return {}; }
  async setLocalDescription() { descriptions++; }
  close() { closed++; }
}
test('unavailable is not no-leak success', async()=>{
  const r=await collect(url,5,null);
  assert.equal(r.status,'api-unavailable');
});
test('constructor error is explicit', async()=>{
  const r=await collect(url,5,class {constructor(){throw new TypeError('secret');}});
  assert.equal(r.status,'error'); assert.equal(r.error,'TypeError');
  assert(!JSON.stringify(r).includes('secret'));
});
test('synthetic candidates classified without raw addresses', async()=>{
  class Complete extends Peer {
    async setLocalDescription(){
      for(const [address,type] of [['host.local','host'],['192.0.2.1','srflx'],['2001:db8::1','relay']]) {
        this.onicecandidate({candidate:{address,type}});
      }
      this.iceGatheringState='complete'; this.onicegatheringstatechange();
    }
  }
  const r=await collect(url,100,Complete);
  assert.equal(r.status,'gathering-complete');
  assert.equal(r.candidates,3); assert.equal(r.mdns,1); assert.equal(r.literal_ipv4,1);
  assert.equal(r.literal_ipv6,1); assert.equal(r.srflx,1); assert.equal(r.relay,1);
  assert(!JSON.stringify(r).includes('192.0.2.1'));
});
test('timeout closes peer and never marks complete', async()=>{
  const before=closed;
  const r=await collect(url,5,Peer);
  assert.equal(r.status,'inconclusive'); assert.equal(closed,before+1);
});
test('late offer does not touch a closed peer', async()=>{
  class Slow extends Peer { createOffer(){return new Promise(r=>setTimeout(()=>r({}),25));} }
  const before=descriptions;
  const r=await collect(url,5,Slow);
  await new Promise(r=>setTimeout(r,35));
  assert.equal(r.status,'inconclusive'); assert.equal(descriptions,before);
});
test('late rejection is handled after timeout', async()=>{
  class Rejected extends Peer {createOffer(){return new Promise((_,reject)=>setTimeout(()=>reject(new Error('synthetic')),25));}}
  const r=await collect(url,5,Rejected);
  await new Promise(r=>setTimeout(r,35));
  assert.equal(r.status,'inconclusive');
});
test('immediate negotiation rejection closes peer', async()=>{
  class Rejected extends Peer {async createOffer(){throw new Error('secret');}}
  const before=closed;
  const r=await collect(url,100,Rejected);
  assert.equal(r.status,'error'); assert.equal(closed,before+1);
});
