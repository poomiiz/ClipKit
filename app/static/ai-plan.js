window.CKAIPlan = (() => {
  const node = (tag, text) => { const value = document.createElement(tag); if (text !== undefined) value.textContent = text; return value; };
  function render(box, plan) {
    box.setAttribute('aria-busy','false');
    box.classList.add('ai-plan'); box.replaceChildren();
    const action = {preserve:'คง motion เดิม',clear:'ล้าง motion เดิม',replace:'แทนที่ motion'}[plan.motion_action];
    box.append(node('strong', plan.motion_plan.some(item=>item.subject_review_pending) ? 'รอตรวจภาพ' : 'พร้อมตรวจ'), node('p', `ซับ ${plan.lines} · ตัด ${plan.cut} · ${action} (${plan.motion_before || 0} → ${plan.motion_action === 'preserve' ? plan.motion_before || 0 : plan.motion})`));
    function rows(title, items, describe) {
      const details = node('details'), summary = node('summary', `${title} (${items.length})`);
      details.append(summary); box.append(details);
      details.ontoggle = () => {
        if (!details.open || details.children.length > 1) return;
        const table = node('table'), head = node('tr');
        for (const text of ['เวลา','รายการ']) head.append(node('th', text));
        table.append(head);
        for (const item of items) {
          const row = node('tr'), content = node('td'), full = node('details'), excerpt = node('summary', describe(item));
          excerpt.className = 'ai-plan-excerpt'; full.append(excerpt, node('p', describe(item))); content.append(full);
          row.append(node('td', `${item.start.toFixed(2)}–${(item.end ?? item.start + item.duration).toFixed(2)}s`), content);
          table.append(row);
        }
        details.append(table);
      };
    }
    if (plan.motion_plan.length) rows('Motion', plan.motion_plan, item => {
      const params=item.params || {}, words=item.template==='hook-title' ? [params.key,params.sub] : item.template==='stat-number' ? [params.number,params.unit,params.label] : item.events?.map(event=>event.text) || [item.text];
      const policy=item.ownership, roles={normal:'ปกติ',emphasis:'คำเน้น',caption:'ซับแปล',second:'บรรทัดสอง',title:'หัวคลิป'};
      return `${item.template} · ${words.filter(Boolean).join(' ')}\n${item.reason}`
        + (policy ? `\nบทบาท: ${{decorate:'ประกอบ',replace:'แทน',full_card:'เต็มภาพ'}[policy.mode]} ${policy.targets.flatMap(target=>target.roles.map(role=>roles[role]||role)).join(', ')} · ซับแปล: ${{preserve:'คง',replace:'แทน',hide:'ซ่อน'}[policy.caption_policy]}` : '')
        + (item.canvas ? `\nภาพ ${item.canvas.width}×${item.canvas.height} · กรอบ ${item.bounds.map(value=>value.toFixed(1)).join(', ')}` : '')
        + (item.subject_review_pending ? '\nยังไม่ได้ระบุเขตตัวแบบ · ต้องดูภาพจริง' : '');
    });
    else box.append(node('p', plan.motion_action === 'preserve' ? 'ไม่มีการเปลี่ยน motion' : 'ไม่มี motion ในแผน'));
    rows('ข้อความตามเวลา', plan.subtitle_events, item => `${item.role} · ${item.text}`);
    if (plan.hook.length) {
      const details = node('details'); details.append(node('summary','หัวคลิป'),node('p',plan.hook.map(item=>item.text).join(' / '))); box.append(details);
    }
  }
  function review(input, button, box, preview) {
    let checked = '', generation = 0;
    const clear = () => { checked = ''; generation++; box.replaceChildren(); box.setAttribute('aria-busy','false'); button.textContent = 'ตรวจแผน'; };
    input.addEventListener('input', clear);
    return {clear, async check(answer, prepared) {
      if (checked === answer) return true;
      const current = generation;
      button.textContent = 'กำลังตรวจ…';
      box.classList.add('ai-plan'); box.setAttribute('aria-busy','true');
      const placeholders=[node('div'),node('div')];
      for (const value of placeholders) { value.className='ai-plan-skeleton'; value.setAttribute('aria-hidden','true'); }
      box.replaceChildren(...placeholders);
      const plan = prepared || await preview(answer);
      if (current !== generation || input.value !== answer || !input.isConnected) return false;
      render(box, plan); checked = answer; button.textContent = 'ใช้แผนนี้'; return false;
    }};
  }
  return {render, review};
})();
