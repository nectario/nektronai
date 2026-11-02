(() => {
  const tours = {
    inbox: ['01 / YOUR MAILBOXES','Gmail. Personal. Business. All within reach.','Bring Gmail and other supported accounts into one Windows email application. Keep each mailbox’s folders and identity, and move between them without switching apps. Gmail preview access requires approval.','overview-light.webp','Light-theme Nektron Mail workspace with sample accounts and messages.','Your mailboxes, with room to breathe.'],
    search: ['02 / FIND A CONVERSATION','Find the conversation. Keep your train of thought.','Search saved mail in the selected mailbox by sender, recipient, Cc, Bcc, subject or date. Sort results by date or folder, and open a message in its own window while your results stay within reach.','search.webp?v=20261102-search131','Local mail search with visible Cc, Bcc and correspondent fields, results from several sample folders, and a message preview.','Precise local search in your selected mailbox.'],
    compose: ['03 / WRITE WITH FOCUS','Give your words their own space.','Open a separate composer, add recipients and attachments, and save your draft. Your mailbox stays available while you write.','compose.webp','Nektron Mail composer with a clearly labeled subject and sample message.','An independent writing space.'],
    rules: ['04 / MAKE IT YOUR OWN','Write your rules in plain English.','Describe a supported read-state rule, review the proposal, and refine it in the same editor as your manual changes. AI assistance requires eligible account access; you choose when to apply a rule.','rules.webp','Nektron Mail rules editor showing a sample folder rule and AI prompt.','Describe. Review. Apply. Client rules run while Mail is open.'],
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
  function revealLinkedQuestion(hash) {
    const target=document.getElementById(hash.slice(1));
    if(target?.matches('.mail-faq details')) target.open=true;
  }
  document.querySelectorAll('a[href^="#"]').forEach(link=>link.addEventListener('click',()=>revealLinkedQuestion(link.hash)));
  revealLinkedQuestion(location.hash);
  window.addEventListener('hashchange',()=>revealLinkedQuestion(location.hash));
  const dialog=document.querySelector('#screenshot-viewer');
  if (dialog && typeof dialog.showModal==='function') {
    document.querySelectorAll('[data-expand]').forEach(link=>link.addEventListener('click',event=>{
      event.preventDefault();const image=dialog.querySelector('img');image.src=link.href;image.alt=link.querySelector('img').alt;
      dialog.showModal();
    }));
    dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
  }
})();
