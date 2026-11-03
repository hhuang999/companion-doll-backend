'use strict';
const labels={academic:'学业',social_evaluative:'社会评价',relationship:'关系',future:'未来',self:'自我压力',rumination:'反复想',self_criticism:'自我批评',sleep:'睡眠',loneliness:'孤独'};
const contexts={unsafe_relationship:'关系不安全',no_private_space:'缺少隐私',bedtime:'睡前',limited_time:'时间有限',body_focus_distress:'身体关注引发不适',safe_contact:'已确认相对安全的联系人'};
const element=(tag,text,className)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;};
const list=(items,ordered=false)=>{const node=element(ordered?'ol':'ul');items.forEach(text=>node.append(element('li',text)));return node;};
const base='https://github.com/hhuang999/companion-doll-backend/blob/';
async function start(){
 const response=await fetch('assets/project-data.json');if(!response.ok)throw new Error(`内容目录 HTTP ${response.status}`);
 const data=await response.json();
 document.querySelectorAll('[data-source]').forEach(a=>{a.href=base+data.revision+'/'+a.dataset.source;});
 const revision=document.querySelector('#revision');revision.textContent=data.revision.slice(0,12);revision.href='https://github.com/hhuang999/companion-doll-backend/tree/'+data.revision;
 document.querySelector('#content-version').textContent=data.catalog_version;
 const sources=new Map(data.sources.map(source=>[source.id,source]));
 function render(){
  const pressure=document.querySelector('#pressure').value,pathway=document.querySelector('#pathway').value,intent=document.querySelector('#intent').value;
  const cards=data.cards.filter(card=>(!pressure||card.targets.pressure_types.includes(pressure))&&(!pathway||card.targets.pathways.includes(pathway)));
  const catalog=document.querySelector('#catalog');catalog.replaceChildren();
  if(intent!=='explore'||!cards.length){
   const empty=element('article',undefined,'empty');empty.append(element('h3',intent==='quiet'?'可以就停在这里。':intent==='listen'?'先听你说，不安排办法。':'这个组合没有直接映射的策略。'),element('p',intent==='explore'?'运行时会保留倾听，或只澄清一个必要信息；不会为了命中目录而忽略排除条件。':'尊重当下的意愿，无需完成练习或作出行动承诺。'));catalog.append(empty);
  }else cards.forEach(card=>{
   const article=element('article',undefined,'strategy');article.append(element('span',`${card.id} / ${card.protocol.version}`,'code'),element('h3',card.name),element('p',card.protocol.mechanism),element('p',[...card.targets.pressure_types,...card.targets.pathways].map(key=>labels[key]||key).join(' · '),'labels'));
   const details=element('details');details.append(element('summary','适用条件、步骤与退出'));
   details.append(element('h4','开始之前'),list(card.protocol.prerequisites));
   if(card.protocol.required_contexts.length)details.append(element('p','必要情境：'+card.protocol.required_contexts.map(key=>contexts[key]||key).join('、')));
   details.append(element('h4','具体怎么做'),list(card.steps,true),element('p',card.examples[0],'example'),element('h4','什么时候不做'),list(card.not_when),element('h4','退出与反馈'),element('p',card.protocol.stop),element('p',card.protocol.feedback_limits));
   const links=element('div',undefined,'source-links');card.protocol.evidence_ids.forEach(id=>{const source=sources.get(id);if(source){const a=element('a',id+' ↗');a.href=source.url;links.append(a);}});const code=element('a','配置源码 ↗');code.href=base+data.revision+'/'+card.path;links.append(code);details.append(links);article.append(details);catalog.append(article);
  });
  document.querySelector('#catalog-status').textContent=intent==='explore'?`${cards.length} / ${data.cards.length} 项内容映射 · 实际执行还需情境筛选、评审和明确许可`:'当前选择不进入行动目录';
 }
 ['pressure','pathway','intent'].forEach(id=>document.querySelector('#'+id).addEventListener('change',render));
 document.querySelector('#reset').addEventListener('click',()=>{document.querySelector('#pressure').value='';document.querySelector('#pathway').value='';document.querySelector('#intent').value='explore';render();});render();
 data.exercises.forEach(item=>{const article=element('article');article.append(element('h3',item.name),element('p',item.protocol.goal),element('p',item.protocol.invitation),list(item.protocol.prerequisites));document.querySelector('#exercises').append(article);});
 data.sources.forEach(source=>{const article=element('article',undefined,'source-entry');const title=source.citation.replace(/\[([^\]]+)\]\([^)]+\)/g,'$1').replace(/\*\*/g,'');const link=element('a',source.id+' · '+title);link.href=source.url;article.append(link,element('p',source.supports),element('p',`实际读取：${source.read_scope} · 核查日期：${source.checked_on}`));document.querySelector('#source-list').append(article);});
 document.documentElement.dataset.ready='true';
}
start().catch(error=>{document.querySelector('#catalog-status').textContent='目录暂时未能加载，请刷新或从 GitHub 阅读内容配置。';console.error(error);document.documentElement.dataset.ready='error';});
