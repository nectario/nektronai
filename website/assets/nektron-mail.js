(() => {
  const tours = {
    inbox: ['01 / YOUR WORKSPACE','One workspace. Every part of your day.','Show your mailboxes together or focus on one. Choose their order, set your main mailbox, and keep unread counts in view.','overview-light.webp','Light-theme Nektron Mail workspace with sample messages.','Your mailboxes, with room to breathe.'],
    search: ['02 / FIND A CONVERSATION','A better way back to that email.','Add the search fields you need, right where you are. Combine a correspondent, subject or date with local search, and keep the results beside your mail.','search.webp','Local mail search with visible search fields and sample results.','Precise local search. No hidden advanced-search dialog.'],
    compose: ['03 / WRITE WITH FOCUS','Give your words their own space.','Open a separate composer, add recipients and attachments, and save your draft. Your mailbox stays available while you write.','compose.webp','Nektron Mail composer with a clearly labeled subject and sample message.','An independent writing space.'],
    rules: ['04 / MAKE IT YOUR OWN','Your routine, written into a rule.','Choose a folder, conditions and timing. Keep routine notifications read, or mark messages read after leaving a reviewed folder. Eligible accounts can draft rules with AI.','rules.webp','Nektron Mail rules editor showing a sample folder rule.','Client-side rules run while Mail is open.'],
    downloads: ['05 / SEE YOUR PROGRESS','Know what has made it home.','Watch folder progress, pause and resume Get Mail, and check coverage. This non-modal window lets you keep reading while messages are saved.','downloads.webp','Get Mail window showing synthetic folder download progress and coverage.','A clear view of saved mail and remaining work.'],
    dark: ['06 / AFTER HOURS','A quieter kind of contrast.','Switch directly between Light and Dark. Thoughtful surfaces, readable text and distinct icons help the workspace stay comfortable.','overview-dark.webp','Dark-theme Nektron Mail workspace with sample messages.','The same workspace, in a different light.']
  };
  const tabs = [...document.querySelectorAll('[data-tour]')];
  function select(tab) {
    const [number,title,description,file,alt,caption] = tours[tab.dataset.tour];
    for (const button of tabs) { const active=button===tab; button.setAttribute('aria-selected',String(active)); button.tabIndex=active?0:-1; }
    document.querySelector('#tour-panel').setAttribute('aria-labelledby',tab.id);
    document.querySelector('#tour-number').textContent=number;
    document.querySelector('#tour-title').textContent=title;
    document.querySelector('#tour-description').textContent=description;
    const image=document.querySelector('#tour-image'); image.src='assets/mail/'+file; image.alt=alt;
    document.querySelector('#tour-image-link').href=image.src;
    document.querySelector('#tour-caption').textContent=caption;
  }
  tabs.forEach((tab,index)=>{tab.addEventListener('click',()=>select(tab));tab.addEventListener('keydown',event=>{
    let next;if(event.key==='ArrowRight')next=(index+1)%tabs.length;else if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=tabs.length-1;else return;
    event.preventDefault();select(tabs[next]);tabs[next].focus();
  });});
  const dialog=document.querySelector('#screenshot-viewer');
  if (dialog && typeof dialog.showModal==='function') {
    document.querySelectorAll('[data-expand]').forEach(link=>link.addEventListener('click',event=>{
      event.preventDefault();const image=dialog.querySelector('img');image.src=link.href;image.alt=link.querySelector('img').alt;
      dialog.showModal();
    }));
    dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
  }
})();
