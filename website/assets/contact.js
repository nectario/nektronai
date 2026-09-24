(() => {
  if (['www.nektron.ai','nektron.com','www.nektron.com'].includes(location.hostname)) {
    location.replace('https://nektron.ai/contact.html');
    return;
  }
  const form=document.querySelector('[data-contact-form]');
  const button=form.querySelector('[type=submit]');
  const status=document.querySelector('[data-contact-status]');
  const retry=document.querySelector('[data-contact-retry]');
  let csrf='', busy=false;
  function report(text) { status.textContent=text; }
  async function prepare() {
    retry.hidden=true;
    button.disabled=true;
    try {
      const r=await fetch('/api/account/csrf',{credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000)});
      if(!r.ok) throw Error();
      csrf=(await r.json()).csrfToken;
      if(!csrf) throw Error();
      button.disabled=false;
      report('');
    } catch {
      report('The form is temporarily unavailable. Try again, or email info@nektron.ai directly.');
      retry.hidden=false;
    }
  }
  retry.addEventListener('click',prepare);
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    if(busy || !csrf || !form.reportValidity())return;
    const data=Object.fromEntries(new FormData(form));
    for(const key of Object.keys(data))data[key]=data[key].trim();
    if(!data.name || data.message.length<10) {report('Please enter your name and a message of at least 10 characters.');status.focus();return;}
    const body=JSON.stringify(data);
    if(new TextEncoder().encode(body).length>4096) {report('Your message is too large. Please shorten it before sending.');status.focus();return;}
    busy=true;button.disabled=true;button.textContent='Sending...';report('');
    try {
      const r=await fetch('/api/account/contact',{method:'POST',credentials:'same-origin',
        headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body,signal:AbortSignal.timeout(20000)});
      const result=await r.json();
      if(!r.ok || result.sent!==true) {
        if(result.error==='INVALID_CSRF') {csrf='';await prepare();}
        throw Error(result.error || 'CONTACT_UNAVAILABLE');
      }
      form.hidden=true;
      report('Thank you. Your message has been sent to NektronAI.');
    } catch(error) {
      const messages={TRY_LATER:'Too many submissions. Please wait before trying again, or email info@nektron.ai.',
        INVALID_INPUT:'Please check your name, email, topic and message. Remove any unsupported control characters.',
        INVALID_CSRF:'Your form session expired. Please try again.',
        CONTACT_UNAVAILABLE:'We could not confirm delivery. Your message is still here; please try again later or email info@nektron.ai.'};
      report(messages[error.message] || messages.CONTACT_UNAVAILABLE);
    } finally {busy=false;button.disabled=!csrf;button.textContent='Send message';status.focus();}
  });
  window.addEventListener('pageshow',()=>{if(!busy && !form.hidden)prepare();});
})();
