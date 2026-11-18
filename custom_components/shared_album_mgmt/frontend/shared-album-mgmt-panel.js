(()=>{var U=globalThis,O=U.ShadowRoot&&(U.ShadyCSS===void 0||U.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,V=Symbol(),it=new WeakMap,E=class{constructor(t,e,s){if(this._$cssResult$=!0,s!==V)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(O&&t===void 0){let s=e!==void 0&&e.length===1;s&&(t=it.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),s&&it.set(e,t))}return t}toString(){return this.cssText}},rt=r=>new E(typeof r=="string"?r:r+"",void 0,V),D=(r,...t)=>{let e=r.length===1?r[0]:t.reduce((s,i,n)=>s+(o=>{if(o._$cssResult$===!0)return o.cssText;if(typeof o=="number")return o;throw Error("Value passed to 'css' function must be a 'css' function result: "+o+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+r[n+1],r[0]);return new E(e,r,V)},nt=(r,t)=>{if(O)r.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let s=document.createElement("style"),i=U.litNonce;i!==void 0&&s.setAttribute("nonce",i),s.textContent=e.cssText,r.appendChild(s)}},B=O?r=>r:r=>r instanceof CSSStyleSheet?(t=>{let e="";for(let s of t.cssRules)e+=s.cssText;return rt(e)})(r):r;var{is:Ot,defineProperty:Rt,getOwnPropertyDescriptor:zt,getOwnPropertyNames:Lt,getOwnPropertySymbols:Vt,getPrototypeOf:Dt}=Object,R=globalThis,ot=R.trustedTypes,Bt=ot?ot.emptyScript:"",qt=R.reactiveElementPolyfillSupport,S=(r,t)=>r,q={toAttribute(r,t){switch(t){case Boolean:r=r?Bt:null;break;case Object:case Array:r=r==null?r:JSON.stringify(r)}return r},fromAttribute(r,t){let e=r;switch(t){case Boolean:e=r!==null;break;case Number:e=r===null?null:Number(r);break;case Object:case Array:try{e=JSON.parse(r)}catch{e=null}}return e}},lt=(r,t)=>!Ot(r,t),at={attribute:!0,type:String,converter:q,reflect:!1,useDefault:!1,hasChanged:lt};Symbol.metadata??=Symbol("metadata"),R.litPropertyMetadata??=new WeakMap;var f=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=at){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let s=Symbol(),i=this.getPropertyDescriptor(t,s,e);i!==void 0&&Rt(this.prototype,t,i)}}static getPropertyDescriptor(t,e,s){let{get:i,set:n}=zt(this.prototype,t)??{get(){return this[e]},set(o){this[e]=o}};return{get:i,set(o){let h=i?.call(this);n?.call(this,o),this.requestUpdate(t,h,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??at}static _$Ei(){if(this.hasOwnProperty(S("elementProperties")))return;let t=Dt(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(S("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(S("properties"))){let e=this.properties,s=[...Lt(e),...Vt(e)];for(let i of s)this.createProperty(i,e[i])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[s,i]of e)this.elementProperties.set(s,i)}this._$Eh=new Map;for(let[e,s]of this.elementProperties){let i=this._$Eu(e,s);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let s=new Set(t.flat(1/0).reverse());for(let i of s)e.unshift(B(i))}else t!==void 0&&e.push(B(t));return e}static _$Eu(t,e){let s=e.attribute;return s===!1?void 0:typeof s=="string"?s:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let s of e.keys())this.hasOwnProperty(s)&&(t.set(s,this[s]),delete this[s]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return nt(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,s){this._$AK(t,s)}_$ET(t,e){let s=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,s);if(i!==void 0&&s.reflect===!0){let n=(s.converter?.toAttribute!==void 0?s.converter:q).toAttribute(e,s.type);this._$Em=t,n==null?this.removeAttribute(i):this.setAttribute(i,n),this._$Em=null}}_$AK(t,e){let s=this.constructor,i=s._$Eh.get(t);if(i!==void 0&&this._$Em!==i){let n=s.getPropertyOptions(i),o=typeof n.converter=="function"?{fromAttribute:n.converter}:n.converter?.fromAttribute!==void 0?n.converter:q;this._$Em=i;let h=o.fromAttribute(e,n.type);this[i]=h??this._$Ej?.get(i)??h,this._$Em=null}}requestUpdate(t,e,s,i=!1,n){if(t!==void 0){let o=this.constructor;if(i===!1&&(n=this[t]),s??=o.getPropertyOptions(t),!((s.hasChanged??lt)(n,e)||s.useDefault&&s.reflect&&n===this._$Ej?.get(t)&&!this.hasAttribute(o._$Eu(t,s))))return;this.C(t,e,s)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:s,reflect:i,wrapped:n},o){s&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,o??e??this[t]),n!==!0||o!==void 0)||(this._$AL.has(t)||(this.hasUpdated||s||(e=void 0),this._$AL.set(t,e)),i===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,n]of this._$Ep)this[i]=n;this._$Ep=void 0}let s=this.constructor.elementProperties;if(s.size>0)for(let[i,n]of s){let{wrapped:o}=n,h=this[i];o!==!0||this._$AL.has(i)||h===void 0||this.C(i,void 0,n,h)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(s=>s.hostUpdate?.()),this.update(e)):this._$EM()}catch(s){throw t=!1,this._$EM(),s}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};f.elementStyles=[],f.shadowRootOptions={mode:"open"},f[S("elementProperties")]=new Map,f[S("finalized")]=new Map,qt?.({ReactiveElement:f}),(R.reactiveElementVersions??=[]).push("2.1.2");var J=globalThis,dt=r=>r,z=J.trustedTypes,ht=z?z.createPolicy("lit-html",{createHTML:r=>r}):void 0,ft="$lit$",b=`lit$${Math.random().toFixed(9).slice(2)}$`,gt="?"+b,jt=`<${gt}>`,x=document,P=()=>x.createComment(""),T=r=>r===null||typeof r!="object"&&typeof r!="function",Q=Array.isArray,It=r=>Q(r)||typeof r?.[Symbol.iterator]=="function",j=`[ 	
\f\r]`,C=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,ct=/-->/g,ut=/>/g,$=RegExp(`>|${j}(?:([^\\s"'>=/]+)(${j}*=${j}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),pt=/'/g,_t=/"/g,bt=/^(?:script|style|textarea|title)$/i,Z=r=>(t,...e)=>({_$litType$:r,strings:t,values:e}),a=Z(1),ee=Z(2),se=Z(3),w=Symbol.for("lit-noChange"),l=Symbol.for("lit-nothing"),mt=new WeakMap,y=x.createTreeWalker(x,129);function vt(r,t){if(!Q(r)||!r.hasOwnProperty("raw"))throw Error("invalid template strings array");return ht!==void 0?ht.createHTML(t):t}var Ft=(r,t)=>{let e=r.length-1,s=[],i,n=t===2?"<svg>":t===3?"<math>":"",o=C;for(let h=0;h<e;h++){let d=r[h],u,p,c=-1,m=0;for(;m<d.length&&(o.lastIndex=m,p=o.exec(d),p!==null);)m=o.lastIndex,o===C?p[1]==="!--"?o=ct:p[1]!==void 0?o=ut:p[2]!==void 0?(bt.test(p[2])&&(i=RegExp("</"+p[2],"g")),o=$):p[3]!==void 0&&(o=$):o===$?p[0]===">"?(o=i??C,c=-1):p[1]===void 0?c=-2:(c=o.lastIndex-p[2].length,u=p[1],o=p[3]===void 0?$:p[3]==='"'?_t:pt):o===_t||o===pt?o=$:o===ct||o===ut?o=C:(o=$,i=void 0);let g=o===$&&r[h+1].startsWith("/>")?" ":"";n+=o===C?d+jt:c>=0?(s.push(u),d.slice(0,c)+ft+d.slice(c)+b+g):d+b+(c===-2?h:g)}return[vt(r,n+(r[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),s]},M=class r{constructor({strings:t,_$litType$:e},s){let i;this.parts=[];let n=0,o=0,h=t.length-1,d=this.parts,[u,p]=Ft(t,e);if(this.el=r.createElement(u,s),y.currentNode=this.el.content,e===2||e===3){let c=this.el.content.firstChild;c.replaceWith(...c.childNodes)}for(;(i=y.nextNode())!==null&&d.length<h;){if(i.nodeType===1){if(i.hasAttributes())for(let c of i.getAttributeNames())if(c.endsWith(ft)){let m=p[o++],g=i.getAttribute(c).split(b),H=/([.?@])?(.*)/.exec(m);d.push({type:1,index:n,name:H[2],strings:g,ctor:H[1]==="."?F:H[1]==="?"?W:H[1]==="@"?K:k}),i.removeAttribute(c)}else c.startsWith(b)&&(d.push({type:6,index:n}),i.removeAttribute(c));if(bt.test(i.tagName)){let c=i.textContent.split(b),m=c.length-1;if(m>0){i.textContent=z?z.emptyScript:"";for(let g=0;g<m;g++)i.append(c[g],P()),y.nextNode(),d.push({type:2,index:++n});i.append(c[m],P())}}}else if(i.nodeType===8)if(i.data===gt)d.push({type:2,index:n});else{let c=-1;for(;(c=i.data.indexOf(b,c+1))!==-1;)d.push({type:7,index:n}),c+=b.length-1}n++}}static createElement(t,e){let s=x.createElement("template");return s.innerHTML=t,s}};function A(r,t,e=r,s){if(t===w)return t;let i=s!==void 0?e._$Co?.[s]:e._$Cl,n=T(t)?void 0:t._$litDirective$;return i?.constructor!==n&&(i?._$AO?.(!1),n===void 0?i=void 0:(i=new n(r),i._$AT(r,e,s)),s!==void 0?(e._$Co??=[])[s]=i:e._$Cl=i),i!==void 0&&(t=A(r,i._$AS(r,t.values),i,s)),t}var I=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:s}=this._$AD,i=(t?.creationScope??x).importNode(e,!0);y.currentNode=i;let n=y.nextNode(),o=0,h=0,d=s[0];for(;d!==void 0;){if(o===d.index){let u;d.type===2?u=new N(n,n.nextSibling,this,t):d.type===1?u=new d.ctor(n,d.name,d.strings,this,t):d.type===6&&(u=new G(n,this,t)),this._$AV.push(u),d=s[++h]}o!==d?.index&&(n=y.nextNode(),o++)}return y.currentNode=x,i}p(t){let e=0;for(let s of this._$AV)s!==void 0&&(s.strings!==void 0?(s._$AI(t,s,e),e+=s.strings.length-2):s._$AI(t[e])),e++}},N=class r{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,s,i){this.type=2,this._$AH=l,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=s,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=A(this,t,e),T(t)?t===l||t==null||t===""?(this._$AH!==l&&this._$AR(),this._$AH=l):t!==this._$AH&&t!==w&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):It(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==l&&T(this._$AH)?this._$AA.nextSibling.data=t:this.T(x.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:s}=t,i=typeof s=="number"?this._$AC(t):(s.el===void 0&&(s.el=M.createElement(vt(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===i)this._$AH.p(e);else{let n=new I(i,this),o=n.u(this.options);n.p(e),this.T(o),this._$AH=n}}_$AC(t){let e=mt.get(t.strings);return e===void 0&&mt.set(t.strings,e=new M(t)),e}k(t){Q(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,s,i=0;for(let n of t)i===e.length?e.push(s=new r(this.O(P()),this.O(P()),this,this.options)):s=e[i],s._$AI(n),i++;i<e.length&&(this._$AR(s&&s._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let s=dt(t).nextSibling;dt(t).remove(),t=s}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},k=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,s,i,n){this.type=1,this._$AH=l,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=n,s.length>2||s[0]!==""||s[1]!==""?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=l}_$AI(t,e=this,s,i){let n=this.strings,o=!1;if(n===void 0)t=A(this,t,e,0),o=!T(t)||t!==this._$AH&&t!==w,o&&(this._$AH=t);else{let h=t,d,u;for(t=n[0],d=0;d<n.length-1;d++)u=A(this,h[s+d],e,d),u===w&&(u=this._$AH[d]),o||=!T(u)||u!==this._$AH[d],u===l?t=l:t!==l&&(t+=(u??"")+n[d+1]),this._$AH[d]=u}o&&!i&&this.j(t)}j(t){t===l?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},F=class extends k{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===l?void 0:t}},W=class extends k{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==l)}},K=class extends k{constructor(t,e,s,i,n){super(t,e,s,i,n),this.type=5}_$AI(t,e=this){if((t=A(this,t,e,0)??l)===w)return;let s=this._$AH,i=t===l&&s!==l||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,n=t!==l&&(s===l||i);i&&this.element.removeEventListener(this.name,this,s),n&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},G=class{constructor(t,e,s){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(t){A(this,t)}};var Wt=J.litHtmlPolyfillSupport;Wt?.(M,N),(J.litHtmlVersions??=[]).push("3.3.3");var $t=(r,t,e)=>{let s=e?.renderBefore??t,i=s._$litPart$;if(i===void 0){let n=e?.renderBefore??null;s._$litPart$=i=new N(t.insertBefore(P(),n),n,void 0,e??{})}return i._$AI(r),i};var X=globalThis,v=class extends f{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=$t(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return w}};v._$litElement$=!0,v.finalized=!0,X.litElementHydrateSupport?.({LitElement:v});var Kt=X.litElementPolyfillSupport;Kt?.({LitElement:v});(X.litElementVersions??=[]).push("4.2.2");var yt={invalid_link:"That isn't a public iCloud shared album link. In Photos, open the shared album, turn on Public Website, and copy its link.",album_not_found:"Apple doesn't have an album at that link. Its Public Website may have been turned off, or the album was deleted.",album_requires_login:"This album is shared with people only. Turn on Public Website for it in Photos.",apple_error:"Apple sent an answer that couldn't be read. Try again in a few minutes.",cannot_connect:"Couldn't reach iCloud. Check Home Assistant's internet connection.",incomplete_listing:"Apple stopped part way through the album, so nothing was removed. Try again in a few minutes.",untrusted_host:"Apple returned an unexpected {kind} host, {host}. If it belongs to Apple, trust it here, from Repairs, or under Settings > Advanced > Extra trusted hosts.",low_disk_space:"Not enough disk space: {free} MB free, {needed} MB needed. Nothing was downloaded.",download_failed:"{count} file(s) couldn't be downloaded. They'll be tried again next sync.",storage_error:"The album folder couldn't be written: {error}.",already_configured:"This album has already been added.",invalid_folder:"Use a folder inside the media folder, like shared_albums/family.",invalid_host:"Enter host names like p99-ckdatabasews.icloud.com or *.icloud-content.com.",unknown:"Something unexpected went wrong. Check the logs."},Gt={baseline_pending:"First full read recorded. From now on, photos that leave the album are handled by your setting.",empty_listing:"Apple returned an empty album, so nothing was removed.",mass_removal_held:"Most of the album seems to have disappeared at once. Nothing was removed; the next sync must agree first."},xt=[["convert","Convert HEIC to JPEG","Largest version; HEIC becomes JPEG."],["original","Keep originals as-is","Largest version, exactly as Apple stores it."],["dashboard","Apple's smaller JPEG","About 2048 px, smallest files, for dashboards."]],wt=[["quarantine","Quarantine","Move to a hidden .quarantine folder you can restore from."],["keep","Keep","Leave the file where it is."],["delete","Delete","Remove the file."]];function Jt(r,t={}){return r.replace(/\{(\w+)\}/g,(e,s)=>s in t?String(t[s]):e)}function L(r,t={}){return r?Jt(yt[r]??yt.unknown,t):null}function At(r){return Gt[r]??r}function Y(r){let t=Number(r)||0;if(t<1024)return`${t} B`;let e=["KB","MB","GB","TB"],s=t/1024,i=0;for(;s>=1024&&i<e.length-1;)s/=1024,i+=1;let n=s>=100||i===0?0:s>=10?1:2;return`${Number(s.toFixed(n))} ${e[i]}`}function tt(r,t=Date.now()){if(!r)return"never";let e=Date.parse(r);if(Number.isNaN(e))return"never";let s=Math.max(0,Math.round((t-e)/1e3));if(s<45)return"just now";let i=[[60,"minute"],[60,"hour"],[24,"day"]],n=s/60,o="minute";for(let d=1;d<i.length&&n>=i[d][0];d+=1)n/=i[d][0],o=i[d][1];let h=Math.round(n);return`${h} ${o}${h===1?"":"s"} ago`}function kt(r){return!r||!r.total?null:Math.min(100,Math.max(0,Math.round(r.done/r.total*100)))}function et(r){return r.state&&r.state!=="loaded"?{label:"Not running",tone:"off"}:r.syncing?{label:"Syncing",tone:"busy"}:r.last_error?{label:"Needs attention",tone:"error"}:{label:"Up to date",tone:"ok"}}function Et(r){let t=Number(r)||0;return t?t%1440===0?t===1440?"Every day":`Every ${t/1440} days`:t%60===0?t===60?"Every hour":`Every ${t/60} hours`:`Every ${t} minutes`:"Manual only"}function Qt(r){return String(r||"").normalize("NFKD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]+/g,"_").replace(/^_+|_+$/g,"")||"album"}function St(r){return`shared_albums/${Qt(r)}`}function Ct(r){let t=String(r||"").trim();if(!t)return!1;t.includes("://")||(t=`https://${t}`);let e;try{e=new URL(t)}catch{return!1}let s=e.hostname.toLowerCase();return s==="photos.icloud.com"||s==="photos.icloud.com.cn"?/^\/shared\/(album|gallery)\/[A-Za-z0-9_-]{5,64}\/?$/.test(e.pathname):/^(www\.)?icloud\.com(\.cn)?$/.test(s)?e.pathname.startsWith("/sharedalbum")&&/^#[A-Za-z0-9_-]{5,64}/.test(e.hash):!1}function Pt(r){let t=["interval_minutes","keep_days","max_files","min_file_size_kb","min_long_edge","max_concurrent_downloads","min_free_space_mb","jpeg_quality"],e={...r};for(let s of t)s in e&&(e[s]=Number(e[s]));return typeof e.extra_trusted_hosts=="string"&&(e.extra_trusted_hosts=e.extra_trusted_hosts.split(/[\s,]+/).map(s=>s.trim()).filter(Boolean)),e}function Tt(r){let t=encodeURIComponent("app,media-source://media_source");return r?`/media-browser/browser/${t}/${encodeURIComponent(`directory,${r}`)}`:`/media-browser/browser/${t}`}function Mt(r,t){let e=new Set(r);return e.has(t)?e.delete(t):e.add(t),e}function Nt(r){return r.size===0?!1:!(r.size===1&&r.has("hass"))}function Ht(r,t){return r.length?r.find(e=>e.entry_id===t)?.entry_id??r[0].entry_id:null}var _="shared_album_mgmt",Ut=120,st=class extends v{static properties={hass:{attribute:!1},narrow:{type:Boolean},panel:{attribute:!1},_data:{state:!0},_selected:{state:!0},_view:{state:!0},_items:{state:!0},_itemsTotal:{state:!0},_media:{state:!0},_quarantine:{state:!0},_picked:{state:!0},_form:{state:!0},_formErrors:{state:!0},_saving:{state:!0},_adding:{state:!0},_add:{state:!0},_toast:{state:!0},_preview:{state:!0}};constructor(){super(),this._data=null,this._selected=localStorage.getItem(`${_}:album`)||null,this._view="photos",this._items=[],this._itemsTotal=0,this._media="all",this._quarantine=[],this._picked=new Set,this._form=null,this._formErrors={},this._saving=!1,this._adding=!1,this._add=this._emptyAdd(),this._toast=null,this._preview=null,this._unsub=null,this._loadedFor=null}_emptyAdd(){return{url:"",name:"",folder:"",media_dir:"",check:null,busy:!1,hosts:[]}}connectedCallback(){super.connectedCallback(),this._subscribe()}disconnectedCallback(){super.disconnectedCallback(),this._unsub&&(this._unsub.then(t=>t()).catch(()=>{}),this._unsub=null)}shouldUpdate(t){return t.has("hass")&&!this._unsub&&this.hass&&this._subscribe(),Nt(t)}_subscribe(){!this.hass||this._unsub||(this._unsub=this.hass.connection.subscribeMessage(t=>this._onData(t),{type:`${_}/subscribe`}))}_onData(t){let e=this._album;this._data=t;let s=Ht(t.albums,this._selected);s!==this._selected&&this._select(s);let i=this._album;i&&e&&e.entry_id===i.entry_id&&(e.syncing!==i.syncing||e.item_count!==i.item_count||e.quarantine_count!==i.quarantine_count)?this._loadView():i&&this._loadedFor!==i.entry_id&&this._loadView()}get _album(){return this._data?.albums.find(t=>t.entry_id===this._selected)??null}_select(t){this._selected=t,t&&localStorage.setItem(`${_}:album`,t),this._items=[],this._quarantine=[],this._picked=new Set,this._form=null,this._formErrors={},this._loadedFor=null,t&&this._data&&this._loadView()}async _ws(t){return this.hass.connection.sendMessagePromise(t)}async _loadView(){let t=this._album;if(!(!t||t.state!=="loaded"))if(this._loadedFor=t.entry_id,this._view==="photos"){let e=await this._ws({type:`${_}/items`,entry_id:t.entry_id,offset:0,limit:Math.max(Ut,this._items.length),media:this._media});this._items=e.items,this._itemsTotal=e.total}else if(this._view==="quarantine"){let e=await this._ws({type:`${_}/quarantine`,entry_id:t.entry_id});this._quarantine=e.items;let s=new Set(e.items.map(i=>i.id));this._picked=new Set([...this._picked].filter(i=>s.has(i)))}else this._view==="settings"&&!this._form&&(this._form={title:t.title,...t.options},this._form.extra_trusted_hosts=(t.options.extra_trusted_hosts||[]).join(`
`))}async _more(){let t=this._album,e=await this._ws({type:`${_}/items`,entry_id:t.entry_id,offset:this._items.length,limit:Ut,media:this._media});this._items=[...this._items,...e.items],this._itemsTotal=e.total}_setView(t){this._view=t,this._loadView()}_notify(t){this._toast=t,clearTimeout(this._toastTimer),this._toastTimer=setTimeout(()=>{this._toast=null},4e3)}async _sync(t=!1){let e=await this._ws({type:`${_}/sync`,entry_id:this._selected,full:t});this._notify(e.started?t?"Checking every file\u2026":"Sync started":"Already syncing")}async _restore(t){let e=await this._ws({type:`${_}/restore`,entry_id:this._selected,ids:t});this._notify(`Restored ${e.restored.length} file(s). They'll be kept even though they left the album.`),this._picked=new Set,this._loadView()}async _deleteQuarantined(t){if(!confirm(`Delete ${t.length} file(s) for good? This can't be undone.`))return;let e=await this._ws({type:`${_}/delete_quarantined`,entry_id:this._selected,ids:t});this._notify(`Deleted ${e.deleted} file(s).`),this._picked=new Set,this._loadView()}async _trustHost(t,e){let s=[...t.options.extra_trusted_hosts||[]];s.includes(e)||s.push(e);let i=await this._ws({type:`${_}/update_settings`,entry_id:t.entry_id,options:{extra_trusted_hosts:s}});this._notify(i.ok?`Trusted ${e}. The album reloads and syncs again.`:L("invalid_host"))}async _remove(){let t=this._album;confirm(`Remove ${t.title}? Syncing stops. The folder and its photos stay on disk.`)&&(await this._ws({type:`${_}/remove_album`,entry_id:t.entry_id}),this._select(null))}async _save(){this._saving=!0;let{title:t,...e}=this._form;try{let s=await this._ws({type:`${_}/update_settings`,entry_id:this._selected,title:t,options:Pt(e)});s.ok?(this._formErrors={},this._form=null,this._notify("Settings saved. The album reloads with them."),this._view="photos"):this._formErrors=s.errors}finally{this._saving=!1}}async _checkLink(){let t=this._add;if(!Ct(t.url)){this._add={...t,check:{ok:!1,error:"invalid_link"}};return}this._add={...t,busy:!0,check:null};let e={type:`${_}/validate_link`,url:t.url};t.hosts?.length&&(e.extra_trusted_hosts=t.hosts);let s=await this._ws(e),i=t.name||s.name||"";this._add={...this._add,busy:!1,check:s,name:i,folder:t.folder||St(i||"album")}}async _addAlbum(){let t=this._add;this._add={...t,busy:!0};let e={type:`${_}/add_album`,url:t.url};t.name&&(e.name=t.name),t.folder&&(e.folder=t.folder),t.media_dir&&(e.media_dir=t.media_dir),t.hosts?.length&&(e.extra_trusted_hosts=t.hosts);let s=await this._ws(e);s.ok?(this._adding=!1,this._add=this._emptyAdd(),this._select(s.entry_id),this._notify("Album added. The first sync is running.")):this._add={...this._add,busy:!1,check:{ok:!1,...s}}}render(){if(!this._data)return a`<div class="page"><div class="loading">Loading albums…</div></div>`;let t=this._data.albums;return a`
      <div class="page">
        <header>
          <div class="title">
            ${this.narrow?a`<button
                  class="icon menu"
                  aria-label="Open the sidebar"
                  @click=${()=>this.dispatchEvent(new Event("hass-toggle-menu",{bubbles:!0,composed:!0}))}
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z" />
                  </svg>
                </button>`:l}
            <svg viewBox="0 0 24 24" class="logo" aria-hidden="true">
              <path
                d="M22,16V4A2,2 0 0,0 20,2H8A2,2 0 0,0 6,4V16A2,2 0 0,0 8,18H20A2,2 0 0,0 22,16M11,12L13.03,14.71L16,11L20,16H8M2,6V20A2,2 0 0,0 4,22H18V20H4V6"
              />
            </svg>
            <h1>Shared Album Mgmt</h1>
          </div>
          <button class="primary" @click=${()=>this._adding=!this._adding}>
            ${this._adding?"Close":"+ Add album"}
          </button>
        </header>
        ${this._adding||!t.length?this._renderAdd(!t.length):l}
        ${t.length?a`
              <nav class="tabs" role="tablist">
                ${t.map(e=>{let s=et(e);return a`<button
                    role="tab"
                    class="tab ${e.entry_id===this._selected?"active":""}"
                    @click=${()=>this._select(e.entry_id)}
                  >
                    <span class="dot ${s.tone}"></span>${e.title}
                  </button>`})}
              </nav>
              ${this._album?this._renderAlbum(this._album):l}
            `:l}
        ${this._preview?this._renderPreview():l}
        ${this._toast?a`<div class="toast" role="status">${this._toast}</div>`:l}
      </div>
    `}_renderAdd(t){let e=this._add,s=e.check,i=this._data.media_dirs;return a`
      <section class="card add">
        <h2>${t?"Add your first shared album":"Add a shared album"}</h2>
        <p class="muted">
          In Photos, open the shared album, turn on <b>Public Website</b>, and copy its link.
          Both <code>photos.icloud.com/shared/album/…</code> and older
          <code>icloud.com/sharedalbum/#…</code> links work. Anyone with the link can see the
          album, so treat it like a password.
        </p>
        <label
          >Public album link
          <input
            type="url"
            placeholder="https://photos.icloud.com/shared/album/…"
            .value=${e.url}
            @input=${n=>this._add={...e,url:n.target.value,check:null}}
          />
        </label>
        <div class="row">
          <button ?disabled=${!e.url||e.busy} @click=${this._checkLink}>
            ${e.busy&&!s?"Checking\u2026":"Check link"}
          </button>
          ${s&&!s.ok?a`<span class="error-text">${L(s.error,s.placeholders)}</span>`:l}
          ${s?.error==="untrusted_host"&&s.placeholders?.host?a`<button
                @click=${()=>{this._add={...this._add,hosts:[...this._add.hosts||[],s.placeholders.host]},this._checkLink()}}
              >
                Trust ${s.placeholders.host}
              </button>`:l}
          ${s?.ok?a`<span class="ok-text"
                >Found ${s.name?a`<b>${s.name}</b>`:"the album"}: ${s.photos}
                photos, ${s.videos} videos${s.already_added?" (already added)":""}</span
              >`:l}
        </div>
        ${s?.ok&&!s.already_added?a`
              <div class="grid2">
                <label
                  >Name
                  <input
                    .value=${e.name}
                    @input=${n=>this._add={...this._add,name:n.target.value}}
                  />
                </label>
                <label
                  >Media folder
                  <select
                    @change=${n=>this._add={...this._add,media_dir:n.target.value}}
                  >
                    ${i.map(n=>a`<option value=${n} ?selected=${(e.media_dir||i[0])===n}>${n}</option>`)}
                  </select>
                </label>
                <label class="span2"
                  >Folder
                  <input
                    .value=${e.folder}
                    @input=${n=>this._add={...this._add,folder:n.target.value}}
                  />
                </label>
              </div>
              <p class="muted">
                New albums convert HEIC to JPEG, quarantine photos that leave the album, and sync
                every 3 hours. Change any of it under Settings after adding.
              </p>
              <button class="primary" ?disabled=${e.busy} @click=${this._addAlbum}>
                ${e.busy?"Adding\u2026":"Add album"}
              </button>
            `:l}
      </section>
    `}_renderAlbum(t){let e=et(t);if(t.state!=="loaded")return a`<section class="card">
        <h2>${t.title}</h2>
        <p>This album isn't running (${t.state}). Check it under Settings > Devices &amp; services.</p>
      </section>`;let s=kt(t.progress),i=L(t.last_error,t.last_error_placeholders),n=t.last_result?.warnings??[];return a`
      <section class="card status">
        <div class="hero">
          ${t.latest_thumb?a`<img class="latest" src=${t.latest_thumb} alt="Latest photo" />`:a`<div class="latest empty">No photos yet</div>`}
          <div class="summary">
            <div class="row between">
              <h2>${t.title}</h2>
              <span class="chip ${e.tone}">${e.label}</span>
            </div>
            <div class="muted small">
              ${t.kind==="modern"?"photos.icloud.com link":"icloud.com/sharedalbum link"}
              · id ${t.album_id} · ${Et(t.interval)}
            </div>
            ${t.syncing?a`<div class="progress" aria-label="Sync progress">
                    <div
                      class="bar ${s===null?"indeterminate":""}"
                      style="width:${s===null?30:s}%"
                    ></div>
                  </div>
                  <div class="small muted">
                    ${t.progress?.total?`${t.progress.done} of ${t.progress.total} downloaded${t.progress.current?` \xB7 ${t.progress.current}`:""}`:"Reading the album from iCloud\u2026"}
                  </div>`:l}
            <dl class="stats">
              <div><dt>Items</dt><dd>${t.item_count}</dd></div>
              <div><dt>Photos</dt><dd>${t.photo_count}</dd></div>
              <div><dt>Videos</dt><dd>${t.video_count}</dd></div>
              <div><dt>In album</dt><dd>${t.remote_count}</dd></div>
              <div><dt>Space used</dt><dd>${Y(t.bytes_used)}</dd></div>
              <div><dt>Quarantined</dt><dd>${t.quarantine_count}</dd></div>
              <div><dt>Last sync</dt><dd title=${t.last_sync??""}>${tt(t.last_sync)}</dd></div>
            </dl>
            <div class="folder small"><span class="muted">Folder</span> <code>${t.folder}</code></div>
          </div>
        </div>
        ${i?a`<div class="banner error">
              ${i}
              ${t.last_error==="untrusted_host"&&t.last_error_placeholders?.host?a`<div class="row">
                    <button @click=${()=>this._trustHost(t,t.last_error_placeholders.host)}>
                      Trust ${t.last_error_placeholders.host}
                    </button>
                  </div>`:l}
            </div>`:l}
        ${n.map(o=>a`<div class="banner info">${At(o)}</div>`)}
        <div class="row actions">
          <button class="primary" ?disabled=${t.syncing} @click=${()=>this._sync(!1)}>
            Sync now
          </button>
          <button ?disabled=${t.syncing} @click=${()=>this._sync(!0)}>Check every file</button>
          <a class="button" href=${Tt(t.media_content_id)}>Open in Media</a>
          <span class="spacer"></span>
          <button class="danger flat" @click=${this._remove}>Remove album</button>
        </div>
      </section>
      <nav class="subtabs">
        ${[["photos",`Photos (${t.item_count})`],["quarantine",`Quarantine (${t.quarantine_count})`],["settings","Settings"]].map(([o,h])=>a`<button class=${this._view===o?"active":""} @click=${()=>this._setView(o)}>
              ${h}
            </button>`)}
      </nav>
      ${this._view==="photos"?this._renderPhotos():l}
      ${this._view==="quarantine"?this._renderQuarantine():l}
      ${this._view==="settings"?this._renderSettings(t):l}
    `}_thumb(t,e=l){let s=t.media_type==="video";return a`<figure class="thumb ${s?"video":""}">
      <button class="img" @click=${()=>this._preview=t} title=${t.file}>
        ${s?a`<svg viewBox="0 0 24 24"><path d="M8,5.14V19.14L19,12.14L8,5.14Z" /></svg>`:a`<img loading="lazy" src=${t.thumb} alt=${t.file} />`}
      </button>
      ${e}
      <figcaption>
        <span class="name">${t.file}</span>
        <span class="muted">${t.captured_at?t.captured_at.slice(0,10):""} · ${Y(t.size)}</span>
        ${t.pinned?a`<span class="tag">kept</span>`:t.in_album===!1?a`<span class="tag">left album</span>`:l}
      </figcaption>
    </figure>`}_renderPhotos(){return a`
      <section class="card">
        <div class="row between">
          <div class="segmented">
            ${[["all","All"],["image","Photos"],["video","Videos"]].map(([t,e])=>a`<button
                class=${this._media===t?"active":""}
                @click=${()=>{this._media=t,this._items=[],this._loadView()}}
              >
                ${e}
              </button>`)}
          </div>
          <span class="muted small">${this._itemsTotal} file(s)</span>
        </div>
        ${this._items.length?a`<div class="grid">${this._items.map(t=>this._thumb(t))}</div>`:a`<p class="muted center">Nothing here yet. Files appear as soon as the first sync downloads them.</p>`}
        ${this._items.length<this._itemsTotal?a`<div class="center"><button @click=${this._more}>Load more</button></div>`:l}
      </section>
    `}_renderQuarantine(){let t=this._quarantine,e=[...this._picked];return a`
      <section class="card">
        <p class="muted">
          Photos that left the album are moved here instead of being deleted. Restore puts a file
          back in the album folder and keeps it there for good; Delete removes it.
        </p>
        ${t.length?a`
              <div class="row">
                <button
                  @click=${()=>this._picked=e.length===t.length?new Set:new Set(t.map(s=>s.id))}
                >
                  ${e.length===t.length?"Select none":"Select all"}
                </button>
                <button ?disabled=${!e.length} @click=${()=>this._restore(e)}>
                  Restore ${e.length||""}
                </button>
                <button class="danger" ?disabled=${!e.length} @click=${()=>this._deleteQuarantined(e)}>
                  Delete ${e.length||""}
                </button>
              </div>
              <div class="grid">
                ${t.map(s=>this._thumb(s,a`<label class="pick"
                      ><input
                        type="checkbox"
                        .checked=${this._picked.has(s.id)}
                        @change=${()=>this._picked=Mt(this._picked,s.id)}
                      />
                      <span class="small">moved ${tt(s.moved_at)}</span></label
                    >`))}
              </div>
            `:a`<p class="muted center">The quarantine is empty.</p>`}
      </section>
    `}_field(t,e,s,i){let n=this._formErrors[t];return a`<label class=${n?"invalid":""}
      >${e} ${i} ${s?a`<span class="help">${s}</span>`:l}
      ${n?a`<span class="error-text">${this._fieldError(n)}</span>`:l}
    </label>`}_fieldError(t){return{invalid_interval:"Use 0 for manual only, or 15 to 10080 minutes.",nothing_to_sync:"Turn on photos, videos, or both.",invalid_media_dir:"Choose one of Home Assistant's media folders.",invalid_folder:"Use a folder like shared_albums/family. Each part starts with a letter or digit.",invalid_number:"Enter a number in the allowed range.",invalid_host:"Use host names like p99-ckdatabasews.icloud.com or *.icloud-content.com."}[t]??t}_bind(t,e="text"){return s=>{let i=e==="bool"?s.target.checked:s.target.value;this._form={...this._form,[t]:i}}}_number(t,e,s,i=1){return a`<input
      type="number"
      min=${e}
      max=${s}
      step=${i}
      .value=${String(this._form[t]??"")}
      @input=${this._bind(t)}
    />`}_choices(t,e){return a`<div class="choices">
      ${e.map(([s,i,n])=>a`<label class="choice ${this._form[t]===s?"on":""}">
          <input
            type="radio"
            name=${t}
            .checked=${this._form[t]===s}
            @change=${()=>this._form={...this._form,[t]:s}}
          />
          <span><b>${i}</b><br /><span class="muted small">${n}</span></span>
        </label>`)}
    </div>`}_renderSettings(t){let e=this._form;if(!e)return a`<section class="card"><p class="muted">Loading…</p></section>`;let s=this._data.heic_available;return a`
      <section class="card settings">
        <h3>Album</h3>
        <div class="grid2">
          ${this._field("title","Name",null,a`<input .value=${e.title} @input=${this._bind("title")} />`)}
          ${this._field("interval_minutes","Sync every (minutes)","0 = only when you press Sync now.",this._number("interval_minutes",0,10080,5))}
        </div>
        <h3>Photo format</h3>
        ${this._choices("photo_format",xt)}
        ${!s&&e.photo_format==="convert"?a`<div class="banner info">
              HEIC conversion isn't available on this system, so Apple's largest JPEG is saved instead.
            </div>`:l}
        <h3>When a photo leaves the album</h3>
        ${this._choices("leave_mode",wt)}
        <p class="muted small">
          Nothing is removed before the first full read of the album, when Apple returns an empty
          album, or when most of the album disappears at once (the next sync must agree). Files you
          changed by hand are never removed.
        </p>
        <h3>What to save</h3>
        <div class="row">
          <label class="toggle"
            ><input type="checkbox" .checked=${e.sync_photos} @change=${this._bind("sync_photos","bool")} /> Photos</label
          >
          <label class="toggle"
            ><input type="checkbox" .checked=${e.sync_videos} @change=${this._bind("sync_videos","bool")} /> Videos</label
          >
          <label class="toggle"
            ><input type="checkbox" .checked=${e.write_latest} @change=${this._bind("write_latest","bool")} />
            latest.jpg</label
          >
          <label class="toggle"
            ><input type="checkbox" .checked=${e.write_index} @change=${this._bind("write_index","bool")} />
            index.json</label
          >
        </div>
        ${this._formErrors.sync_photos?a`<span class="error-text">${this._fieldError(this._formErrors.sync_photos)}</span>`:l}
        <h3>Folder</h3>
        <div class="grid2">
          ${this._field("media_dir","Media folder",null,a`<select @change=${this._bind("media_dir")}>
              ${this._data.media_dirs.map(i=>a`<option value=${i} ?selected=${e.media_dir===i}>${i}</option>`)}
            </select>`)}
          ${this._field("folder","Folder","Changing it starts a new folder; the old one stays as it is.",a`<input .value=${e.folder} @input=${this._bind("folder")} />`)}
        </div>
        <details>
          <summary>Limits and filters</summary>
          <div class="grid2">
            ${this._field("keep_days","Keep days","Only photos taken in the last N days. 0 = all.",this._number("keep_days",0,36500))}
            ${this._field("max_files","Max files","Only the newest N items. 0 = all.",this._number("max_files",0,1e6))}
            ${this._field("min_file_size_kb","Minimum file size (kB)","0 = no minimum.",this._number("min_file_size_kb",0,1e6))}
            ${this._field("min_long_edge","Minimum long edge (px)","0 = no minimum.",this._number("min_long_edge",0,2e4))}
          </div>
        </details>
        <details>
          <summary>Advanced</summary>
          <div class="grid2">
            ${this._field("extra_trusted_hosts","Extra trusted hosts","One per line. For when Apple starts using a new host. *.example.com covers subdomains.",a`<textarea rows="3" .value=${e.extra_trusted_hosts} @input=${this._bind("extra_trusted_hosts")}></textarea>`)}
            ${this._field("max_concurrent_downloads","Downloads at once",null,this._number("max_concurrent_downloads",1,8))}
            ${this._field("min_free_space_mb","Keep this much disk free (MB)",null,this._number("min_free_space_mb",0,1e7))}
            ${this._field("jpeg_quality","JPEG quality (%)","For photos converted from HEIC.",this._number("jpeg_quality",50,100))}
          </div>
        </details>
        <div class="row actions">
          <button class="primary" ?disabled=${this._saving} @click=${this._save}>
            ${this._saving?"Saving\u2026":"Save"}
          </button>
          <button
            class="flat"
            @click=${()=>{this._form=null,this._formErrors={},this._loadView()}}
          >
            Reset
          </button>
        </div>
      </section>
    `}_renderPreview(){let t=this._preview;return a`<div class="overlay" @click=${()=>this._preview=null}>
      <div class="viewer" @click=${e=>e.stopPropagation()}>
        ${t.media_type==="video"?a`<video src=${t.full} controls autoplay></video>`:a`<img src=${t.full} alt=${t.file} />`}
        <div class="row between">
          <span>${t.file}</span>
          <button class="flat" @click=${()=>this._preview=null}>Close</button>
        </div>
      </div>
    </div>`}static styles=D`
    :host {
      display: block;
      min-height: 100vh;
      background: var(--primary-background-color, #f5f6f8);
      color: var(--primary-text-color, #1c1c1e);
      font-family: var(--paper-font-body1_-_font-family, Roboto, system-ui, sans-serif);
      --accent: var(--primary-color, #03a9f4);
      --card: var(--card-background-color, #fff);
      --muted: var(--secondary-text-color, #6b7280);
      --line: var(--divider-color, rgba(0, 0, 0, 0.12));
      --ok: var(--success-color, #2e7d32);
      --warn: var(--warning-color, #f59e0b);
      --bad: var(--error-color, #d32f2f);
    }
    .page {
      max-width: 1180px;
      margin: 0 auto;
      padding: 16px;
      box-sizing: border-box;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
    }
    .title {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    button.icon.menu {
      padding: 6px;
      border: none;
      background: transparent;
      line-height: 0;
    }
    button.icon.menu svg {
      width: 24px;
      height: 24px;
      fill: currentColor;
    }
    .logo {
      width: 30px;
      height: 30px;
      fill: var(--accent);
    }
    h1 {
      font-size: 22px;
      font-weight: 500;
      margin: 0;
    }
    h2 {
      font-size: 19px;
      margin: 0;
      font-weight: 500;
    }
    h3 {
      font-size: 15px;
      margin: 18px 0 8px;
      font-weight: 600;
    }
    .card {
      background: var(--card);
      border-radius: var(--ha-card-border-radius, 12px);
      box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0, 0, 0, 0.12));
      padding: 16px;
      margin-bottom: 12px;
    }
    .muted {
      color: var(--muted);
    }
    .small {
      font-size: 13px;
    }
    .center {
      text-align: center;
    }
    code {
      font-size: 12.5px;
      background: rgba(127, 127, 127, 0.12);
      padding: 1px 5px;
      border-radius: 4px;
      word-break: break-all;
    }
    button,
    a.button {
      font: inherit;
      font-size: 14px;
      border: 1px solid var(--line);
      background: var(--card);
      color: var(--primary-text-color);
      border-radius: 18px;
      padding: 7px 16px;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    button:disabled {
      opacity: 0.5;
      cursor: default;
    }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: var(--text-primary-color, #fff);
    }
    button.danger {
      color: var(--bad);
      border-color: var(--bad);
    }
    button.flat {
      border-color: transparent;
      background: transparent;
    }
    .row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .row.between {
      justify-content: space-between;
    }
    .spacer {
      flex: 1;
    }
    .actions {
      margin-top: 14px;
    }
    .tabs {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      margin-bottom: 12px;
      padding-bottom: 2px;
    }
    .tab {
      white-space: nowrap;
    }
    .tab.active {
      background: var(--accent);
      border-color: var(--accent);
      color: var(--text-primary-color, #fff);
    }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--muted);
      display: inline-block;
    }
    .dot.ok {
      background: var(--ok);
    }
    .dot.busy {
      background: var(--accent);
      box-shadow: 0 0 0 3px rgba(3, 169, 244, 0.25);
    }
    .dot.error {
      background: var(--bad);
    }
    .tab.active .dot {
      box-shadow: 0 0 0 2px #fff;
    }
    .chip {
      font-size: 12.5px;
      padding: 3px 10px;
      border-radius: 12px;
      background: rgba(127, 127, 127, 0.15);
    }
    .chip.ok {
      background: rgba(46, 125, 50, 0.14);
      color: var(--ok);
    }
    .chip.busy {
      background: rgba(3, 169, 244, 0.14);
      color: var(--accent);
    }
    .chip.error {
      background: rgba(211, 47, 47, 0.12);
      color: var(--bad);
    }
    .hero {
      display: flex;
      gap: 16px;
      align-items: flex-start;
    }
    .latest {
      width: 180px;
      height: 180px;
      object-fit: cover;
      border-radius: 10px;
      flex: none;
      background: rgba(127, 127, 127, 0.12);
    }
    .latest.empty {
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--muted);
      font-size: 13px;
    }
    .summary {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
      gap: 8px;
      margin: 4px 0 0;
    }
    .stats div {
      background: rgba(127, 127, 127, 0.07);
      border-radius: 8px;
      padding: 8px 10px;
    }
    dt {
      font-size: 12px;
      color: var(--muted);
    }
    dd {
      margin: 2px 0 0;
      font-size: 18px;
      font-weight: 500;
    }
    .progress {
      height: 8px;
      border-radius: 4px;
      background: rgba(127, 127, 127, 0.18);
      overflow: hidden;
      position: relative;
    }
    .bar {
      height: 100%;
      background: var(--accent);
      border-radius: 4px;
      transition: width 0.4s ease;
    }
    .bar.indeterminate {
      position: absolute;
      animation: slide 1.4s infinite ease-in-out;
    }
    @keyframes slide {
      from {
        left: -30%;
      }
      to {
        left: 100%;
      }
    }
    .banner {
      margin-top: 12px;
      padding: 10px 12px;
      border-radius: 8px;
      font-size: 14px;
    }
    .banner.error {
      background: rgba(211, 47, 47, 0.1);
      color: var(--bad);
    }
    .banner.info {
      background: rgba(3, 169, 244, 0.1);
    }
    .subtabs {
      display: flex;
      gap: 4px;
      border-bottom: 1px solid var(--line);
      margin: 4px 0 12px;
    }
    .subtabs button {
      border: none;
      border-radius: 0;
      background: transparent;
      padding: 10px 14px;
      border-bottom: 2px solid transparent;
    }
    .subtabs button.active {
      border-bottom-color: var(--accent);
      color: var(--accent);
      font-weight: 500;
    }
    .segmented {
      display: inline-flex;
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
    }
    .segmented button {
      border: none;
      border-radius: 0;
    }
    .segmented button.active {
      background: var(--accent);
      color: var(--text-primary-color, #fff);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
      gap: 10px;
      margin-top: 12px;
    }
    .thumb {
      margin: 0;
      background: rgba(127, 127, 127, 0.06);
      border-radius: 10px;
      overflow: hidden;
      position: relative;
    }
    .thumb .img {
      border: none;
      padding: 0;
      border-radius: 0;
      width: 100%;
      aspect-ratio: 1;
      background: rgba(127, 127, 127, 0.15);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .thumb img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
    .thumb.video svg {
      width: 48px;
      height: 48px;
      fill: var(--muted);
    }
    figcaption {
      padding: 6px 8px 8px;
      display: flex;
      flex-direction: column;
      gap: 2px;
      font-size: 12px;
    }
    .name {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .tag {
      align-self: flex-start;
      font-size: 11px;
      background: rgba(245, 158, 11, 0.18);
      border-radius: 6px;
      padding: 1px 6px;
    }
    .pick {
      position: absolute;
      top: 6px;
      left: 6px;
      background: rgba(0, 0, 0, 0.55);
      color: #fff;
      border-radius: 8px;
      padding: 2px 8px 2px 4px;
      display: flex;
      align-items: center;
      gap: 4px;
    }
    label {
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 13px;
      color: var(--muted);
      margin: 6px 0;
    }
    input,
    select,
    textarea {
      font: inherit;
      font-size: 14px;
      color: var(--primary-text-color);
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px 10px;
    }
    label.invalid input,
    label.invalid select,
    label.invalid textarea {
      border-color: var(--bad);
    }
    .help {
      font-size: 12px;
    }
    .error-text {
      color: var(--bad);
      font-size: 13px;
    }
    .ok-text {
      color: var(--ok);
      font-size: 14px;
    }
    .grid2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0 16px;
    }
    .span2 {
      grid-column: span 2;
    }
    .choices {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 8px;
    }
    .choice {
      flex-direction: row;
      align-items: flex-start;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
      color: var(--primary-text-color);
      cursor: pointer;
      margin: 0;
    }
    .choice.on {
      border-color: var(--accent);
      background: rgba(3, 169, 244, 0.07);
    }
    .toggle {
      flex-direction: row;
      align-items: center;
      color: var(--primary-text-color);
      font-size: 14px;
      margin-right: 12px;
    }
    details {
      margin-top: 14px;
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }
    summary {
      cursor: pointer;
      font-weight: 600;
      font-size: 15px;
    }
    .overlay {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.75);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10;
    }
    .viewer {
      background: var(--card);
      border-radius: 12px;
      padding: 12px;
      max-width: 92vw;
      max-height: 92vh;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .viewer img,
    .viewer video {
      max-width: 88vw;
      max-height: 80vh;
      border-radius: 8px;
    }
    .toast {
      position: fixed;
      bottom: 24px;
      left: 50%;
      transform: translateX(-50%);
      background: #323232;
      color: #fff;
      padding: 10px 18px;
      border-radius: 8px;
      font-size: 14px;
      z-index: 11;
    }
    .loading {
      padding: 48px;
      text-align: center;
      color: var(--muted);
    }
    @media (max-width: 700px) {
      .hero {
        flex-direction: column;
      }
      .latest {
        width: 100%;
        height: 200px;
      }
      .grid2 {
        grid-template-columns: 1fr;
      }
      .span2 {
        grid-column: auto;
      }
      .grid {
        grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
      }
    }
  `};customElements.get("shared-album-mgmt-panel")||customElements.define("shared-album-mgmt-panel",st);})();
/*! Bundled license information:

@lit/reactive-element/css-tag.js:
  (**
   * @license
   * Copyright 2019 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/reactive-element.js:
lit-html/lit-html.js:
lit-element/lit-element.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/is-server.js:
  (**
   * @license
   * Copyright 2022 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)
*/
