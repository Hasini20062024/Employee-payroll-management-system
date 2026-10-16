const API = `${window.location.origin}/api`;
const app = document.querySelector('#app');
const toast = document.querySelector('#toast');
let selectedRole = 'EMPLOYEE';
let toastTimer;
let chatRefreshTimer;

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 4000);
}

function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

function authScreen(mode = 'login') {
  const signup = mode === 'signup';
  app.innerHTML = `
    <div class="login-screen">
      <section class="login-card">
        <div class="brand-mark"><span>h</span></div>
        <p class="eyebrow">HAVEN | PEOPLE &amp; PAYROLL</p>
        <h1>${signup ? 'Create your admin<br><em>account.</em>' : 'A better day at work<br><em>starts here.</em>'}</h1>
        <p class="login-copy">${signup ? 'Set up your company workspace. As its administrator, you can create employee accounts and share their sign-in details.' : 'Your calm, clear space for everything people and payroll.'}</p>
        ${signup ? signupForm() : loginForm()}
        <p class="secure">Secure access to your workspace</p>
      </section>
      <aside class="login-art" aria-label="People first">
        <div class="art-orb orb-one"></div><div class="art-orb orb-two"></div>
        <div class="quote-card"><span>&#10022;</span><p>Great teams start with<br>feeling taken care of.</p><span>People first. Always.</span></div>
        <div class="art-note"><div class="avatar-group"><i>MP</i><i>AR</i><i>SK</i></div><span>Made for the people<br>who make it happen.</span></div>
      </aside>
    </div>`;
  if (signup) {
    document.querySelector('#signup-form').addEventListener('submit', register);
    document.querySelector('#back-to-login').addEventListener('click', () => authScreen('login'));
  } else {
    document.querySelectorAll('[data-role]').forEach(button => button.addEventListener('click', () => {
      selectedRole = button.dataset.role;
      document.querySelectorAll('[data-role]').forEach(item => item.classList.toggle('active', item === button));
      document.querySelector('#login-submit').textContent = `Sign in as ${selectedRole === 'EMPLOYEE' ? 'employee' : 'administrator'}`;
    }));
    document.querySelector('#login-form').addEventListener('submit', login);
    document.querySelector('#show-signup').addEventListener('click', () => authScreen('signup'));
    document.querySelector('#forgot-password').addEventListener('click', resetPassword);
  }
}

function loginForm() {
  return `<div class="auth-role-picker" role="group" aria-label="Choose account type">
    <button type="button" data-role="EMPLOYEE" class="${selectedRole === 'EMPLOYEE' ? 'active' : ''}">Employee</button>
    <button type="button" data-role="ADMIN" class="${selectedRole === 'ADMIN' ? 'active' : ''}">Administrator</button>
  </div>
  <form id="login-form">
    <label>Work email or username<input name="username" required placeholder="you@company.com" autocomplete="username"></label>
    <label>Password<input type="password" name="password" required placeholder="Enter your password" autocomplete="current-password"></label>
    <div class="login-row"><label class="check-label"><input type="checkbox"> Remember me</label><button id="forgot-password" class="text-button" type="button">Forgot password?</button></div>
    <button id="login-submit" class="primary full">Sign in as ${selectedRole === 'EMPLOYEE' ? 'employee' : 'administrator'} ?</button>
  </form>
  <p class="auth-switch">New administrator? <button id="show-signup" type="button">Sign up as a new admin</button></p><p class="auth-switch">Employees do not sign up here. Their company admin creates their account and shares their email and temporary password.</p>`;
}

function signupForm() {
  return `<form id="signup-form">
    <label>Company name<input name="company_name" required maxlength="150" autocomplete="organization"></label>
    <div class="auth-name-row"><label>First name<input name="first_name" required autocomplete="given-name"></label><label>Last name<input name="last_name" required autocomplete="family-name"></label></div>
    <label>Work email<input name="email" type="email" required placeholder="you@company.com" autocomplete="email"></label>
    <label>Password<input name="password" type="password" required minlength="8" placeholder="At least 8 characters" autocomplete="new-password"></label>
    <label>Confirm password<input name="confirm_password" type="password" required minlength="8" placeholder="Enter your password again" autocomplete="new-password"></label>
    <button class="primary full">Create admin account and workspace</button>
  </form><p class="auth-switch">Already have an account? <button id="back-to-login" type="button">Sign in</button></p>`;
}

async function login(event) {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  try {
    const response = await fetch(`${API}/auth/token/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: values.username, password: values.password }) });
    const tokens = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(tokens.detail || 'Invalid email or password.');
    const meResponse = await fetch(`${API}/auth/me/`, { headers: { Authorization: `Bearer ${tokens.access}` } });
    const user = await meResponse.json().catch(() => ({}));
    if (!meResponse.ok) throw new Error('Could not verify this account. Please try again.');
    if (user.role !== selectedRole) throw new Error(`This account is not registered as ${selectedRole === 'EMPLOYEE' ? 'an employee' : 'an administrator'}.`);
    saveSession(tokens, user);
  } catch (error) { showToast(error.message); }
}

async function register(event) {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  if (values.password !== values.confirm_password) return showToast('Passwords do not match.');
  try {
    const response = await fetch(`${API}/auth/register-company/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ company_name: values.company_name, first_name: values.first_name, last_name: values.last_name, email: values.email, password: values.password }) });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(Array.isArray(result.detail) ? result.detail.join(' ') : result.detail || 'Unable to create your account.');
    const meResponse = await fetch(`${API}/auth/me/`, { headers: { Authorization: `Bearer ${result.access}` } });
    const user = await meResponse.json().catch(() => ({}));
    if (!meResponse.ok) throw new Error('Your account was created, but sign-in failed. Please sign in.');
    saveSession(result, user);
  } catch (error) { showToast(error.message); }
}

function saveSession(tokens, user) {
  localStorage.setItem('epms_access', tokens.access);
  localStorage.setItem('epms_refresh', tokens.refresh);
  showWorkspace(user);
}

function forcePasswordChange(user) {
  app.innerHTML=`<div class="login-screen"><section class="login-card"><div class="brand-mark"><span>h</span></div><p class="eyebrow">HAVEN | ACCOUNT SECURITY</p><h1>Set a new<br><em>password.</em></h1><p class="login-copy">Your administrator created this account. Change the temporary password before continuing.</p><form id="force-password-form"><label>Temporary password<input name="old_password" type="password" required autocomplete="current-password"></label><label>New password<input name="new_password" type="password" required minlength="8" autocomplete="new-password"></label><label>Confirm new password<input name="confirm_password" type="password" required minlength="8" autocomplete="new-password"></label><button class="primary full">Save new password</button></form><p class="secure">Contact your company administrator if you need a new temporary password.</p></section><aside class="login-art"><div class="art-orb orb-one"></div><div class="quote-card"><span>&#10022;</span><p>Your company,<br>your workspace.</p><span>People first. Always.</span></div></aside></div>`;
  document.querySelector('#force-password-form').addEventListener('submit',async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.currentTarget));if(data.new_password!==data.confirm_password){showToast('The passwords do not match.');return;}try{const response=await fetch(`${API}/auth/change-password/`,{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${localStorage.getItem('epms_access')}`},body:JSON.stringify({old_password:data.old_password,new_password:data.new_password})});const result=await response.json().catch(()=>({}));if(!response.ok)throw new Error(Array.isArray(result.detail)?result.detail.join(' '):result.detail||'Could not change your password.');const meResponse=await fetch(`${API}/auth/me/`,{headers:{Authorization:`Bearer ${localStorage.getItem('epms_access')}`}});const currentUser=await meResponse.json();showToast('Password updated. Welcome to your company workspace.');showWorkspace(currentUser);}catch(error){showToast(error.message);}});
}

async function resetPassword() {
  const email = window.prompt('Enter your work email');
  if (!email) return;
  try {
    await fetch(`${API}/auth/password-reset/request/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) });
    const otp = window.prompt('Enter the 6-digit code sent to your email');
    if (!otp) return;
    const new_password = window.prompt('Enter a new password (at least 8 characters)');
    if (!new_password) return;
    const response = await fetch(`${API}/auth/password-reset/verify/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, otp, new_password }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Could not reset your password.');
    showToast(result.detail);
  } catch (error) { showToast(error.message); }
}


async function apiRequest(path, options = {}) {
  const access = localStorage.getItem('epms_access');
  const isFormData = options.body instanceof FormData;
  const response = await fetch(`${API}${path}`, { ...options, headers: { ...(isFormData ? {} : { 'Content-Type': 'application/json' }), Authorization: `Bearer ${access}`, ...(options.headers || {}) } });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(Array.isArray(result.detail) ? result.detail.join(' ') : result.detail || 'Request failed.');
  return result;
}

function localDateString() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
}

function punchTime(value) {
  return value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--';
}

function getDeviceLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('This browser does not support location services.'));
    navigator.geolocation.getCurrentPosition(
      position => resolve({ latitude: position.coords.latitude, longitude: position.coords.longitude }),
      error => reject(new Error(error.code === 1 ? 'Allow location access in your browser and turn on device location.' : 'Could not get your location. Turn on location and try again.')),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
  });
}

async function renderPeople() {
  const panel=document.querySelector('.auth-welcome');
  panel.innerHTML=`<div class="panel-head"><div><h2>People</h2><p>Employees in ${escapeHtml(window.currentUser?.company_name||'your company')}.</p></div><div class="people-header-actions"><span class="people-count" id="people-count">Loading…</span><button type="button" class="primary" id="add-employee-button">Add employee</button></div></div><form id="people-filter-form" class="people-filter-form"><label class="people-search">Search<input name="search" type="search" placeholder="Name, email, employee ID, job title…"></label><label>Department<select name="department__name"><option value="">All departments</option></select></label><label>Status<select name="status"><option value="">All statuses</option><option>Active</option><option>On Leave</option><option>Suspended</option><option>Resigned</option><option>Terminated</option></select></label><button class="primary" type="submit">Search</button><button class="secondary" type="reset">Clear</button></form><div id="people-directory"><p>Loading employees...</p></div>`;
  const form=panel.querySelector('#people-filter-form');
  try {
    const [allEmployees,departments]=await Promise.all([apiRequest('/employees/'),apiRequest('/departments/')]);
    form.querySelector('[name="department__name"]').innerHTML='<option value="">All departments</option>'+departments.map(department=>`<option value="${escapeHtml(department.name)}">${escapeHtml(department.name)}</option>`).join('');
    const applyFilters=async()=>{
      const params=new URLSearchParams();for(const [key,value] of new FormData(form))if(String(value).trim())params.set(key,String(value).trim());
      const directory=document.querySelector('#people-directory');directory.innerHTML='<p>Searching employees...</p>';
      try { renderPeopleTable(await apiRequest(`/employees/${params.size?'?'+params.toString():''}`)); }
      catch(error) { directory.innerHTML=`<p class="form-error">${escapeHtml(error.message)}</p>`; }
    };
    form.addEventListener('submit',event=>{event.preventDefault();applyFilters();});
    form.querySelectorAll('select').forEach(select=>select.addEventListener('change',applyFilters));
    form.addEventListener('reset',()=>setTimeout(applyFilters,0));
    panel.querySelector('#add-employee-button').addEventListener('click',()=>openCreateEmployeeModal(departments,async()=>{const fresh=await apiRequest('/employees/');renderPeopleTable(fresh);}));
    renderPeopleTable(allEmployees);
  } catch(error) { document.querySelector('#people-directory').innerHTML=`<p class="form-error">${escapeHtml(error.message)}</p>`; }
}

function openCreateEmployeeModal(departments,onCreated) {
  const modal=document.createElement('div');modal.className='modal-backdrop';
  modal.innerHTML=`<section class="modal" role="dialog" aria-modal="true" aria-labelledby="create-employee-title"><div class="modal-header"><div><span class="eyebrow">COMPANY TEAM</span><h2 id="create-employee-title">Add an employee</h2></div><button type="button" class="icon-btn" data-close-employee aria-label="Close">×</button></div><form id="create-employee-form"><div class="form-row"><label>First name<input name="first_name" required maxlength="50"></label><label>Last name<input name="last_name" required maxlength="50"></label></div><label>Work email<input name="email" type="email" required autocomplete="email"></label><div class="form-row"><label>Department<select name="department"><option value="">Not assigned</option>${departments.map(department=>`<option value="${department.id}">${escapeHtml(department.name)}</option>`).join('')}</select></label><label>Job title<input name="designation" maxlength="100" placeholder="For example, Designer"></label></div><div class="confirm-note"><p>The employee will receive a temporary password and must change it before opening their workspace. Share the password securely; it will only be shown once.</p></div><div class="modal-actions"><button type="button" class="secondary" data-close-employee>Cancel</button><button type="submit" class="primary">Create account</button></div></form></section>`;
  document.body.append(modal);modal.querySelectorAll('[data-close-employee]').forEach(button=>button.addEventListener('click',()=>modal.remove()));modal.addEventListener('click',event=>{if(event.target===modal)modal.remove();});
  modal.querySelector('#create-employee-form').addEventListener('submit',async event=>{event.preventDefault();const button=event.currentTarget.querySelector('[type="submit"]');const data=Object.fromEntries(new FormData(event.currentTarget));button.disabled=true;button.textContent='Creating...';try{const employee=await apiRequest('/employees/',{method:'POST',body:JSON.stringify(data)});modal.querySelector('.modal').innerHTML=`<div class="modal-header"><div><span class="eyebrow">ACCOUNT CREATED</span><h2>Share these login details</h2></div><button type="button" class="icon-btn" data-close-employee aria-label="Close">×</button></div><div class="credential-card"><p>Give these details to <b>${escapeHtml(employee.first_name)} ${escapeHtml(employee.last_name)}</b>. Their temporary password will not be shown again.</p><label>Company sign-in email<span>${escapeHtml(employee.user.email)}</span></label><label>Temporary password<span id="temporary-password-value">${escapeHtml(employee.temporary_password)}</span></label><p class="credential-note">They must choose a new password on first sign-in.</p><div class="modal-actions"><button type="button" class="secondary" id="copy-credentials">Copy login details</button><button type="button" class="primary" data-close-employee>Done</button></div></div>`;modal.querySelectorAll('[data-close-employee]').forEach(control=>control.addEventListener('click',()=>modal.remove()));modal.querySelector('#copy-credentials').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(`Haven sign-in email: ${employee.user.email}\nTemporary password: ${employee.temporary_password}`);showToast('Login details copied.');}catch{showToast('Copy unavailable. Select and copy the login details.');}});showToast('Employee account created.');await onCreated();}catch(error){showToast(error.message);button.disabled=false;button.textContent='Create account';}});
}

async function renderCalendar(user,month=localDateString().slice(0,7)) {
  clearInterval(chatRefreshTimer);
  const panel=document.querySelector('.auth-welcome');
  panel.innerHTML=`<div class="panel-head"><div><h2>Company calendar</h2><p>${user.role==='ADMIN'?'Add and maintain company holidays. Employees see the same calendar.':'Company holidays and important dates shared by your administrator.'}</p></div></div><div id="calendar-panel-body"><p>Loading calendar...</p></div>`;
  try { renderCalendarView(user,await apiRequest('/holidays/'),month); }
  catch(error) { document.querySelector('#calendar-panel-body').innerHTML=`<p class="form-error">${escapeHtml(error.message)}</p>`; }
}

function renderCalendarView(user,holidays,month) {
  const body=document.querySelector('#calendar-panel-body');if(!body)return;
  const [year,monthNumber]=month.split('-').map(Number);const firstDay=new Date(year,monthNumber-1,1);const daysInMonth=new Date(year,monthNumber,0).getDate();const offset=(firstDay.getDay()+6)%7;
  const mondayNames=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const visible=holidays.filter(holiday=>holiday.date?.startsWith(month)).sort((a,b)=>a.date.localeCompare(b.date));
  const eventsByDate=new Map(visible.map(holiday=>[holiday.date,holiday]));
  const cells=Array.from({length:42},(_,index)=>{const day=index-offset+1;const date=new Date(year,monthNumber-1,day);const key=`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;const inMonth=date.getMonth()===monthNumber-1;const holiday=eventsByDate.get(key);const type=holiday?.kind?.toLowerCase()==='tentative'?'tentative':'fixed';return `<div class="calendar-day ${inMonth?'':'outside-month'} ${holiday?`has-holiday ${type}`:''} ${key===localDateString()?'is-today':''}"><span class="calendar-day-number">${date.getDate()}</span>${holiday?`<div class="calendar-event ${type}"><i></i><span>${escapeHtml(holiday.name)}</span>${user.role==='ADMIN'?`<button type="button" data-edit-holiday="${holiday.id}" aria-label="Edit ${escapeHtml(holiday.name)}">Edit</button>`:''}</div>`:''}</div>`;}).join('');
  const adminForm=user.role==='ADMIN'?`<form id="holiday-create-form" class="holiday-create-form"><div class="calendar-section-heading"><div><h3>Add a company holiday</h3><p>Employees will see whether the date is fixed or tentative.</p></div></div><div class="holiday-fields"><label>Holiday name<input name="name" maxlength="100" required placeholder="For example, Founders Day"></label><label>Date<input name="date" type="date" value="${month}-01" required></label><label>Status<select name="kind"><option value="Fixed">Fixed</option><option value="Tentative">Tentative</option></select></label><label class="holiday-description">Note (optional)<input name="description" placeholder="Details for employees"></label><button class="primary" type="submit">Add holiday</button></div></form>`:'';
  body.innerHTML=`${adminForm}<div class="calendar-toolbar"><button type="button" class="secondary" id="calendar-prev" aria-label="Previous month">‹</button><h3>${escapeHtml(firstDay.toLocaleDateString(undefined,{month:'long',year:'numeric'}))}</h3><button type="button" class="secondary" id="calendar-next" aria-label="Next month">›</button><button type="button" class="secondary calendar-today" id="calendar-today">Today</button><div class="calendar-legend"><span><i class="legend-fixed"></i>Fixed</span><span><i class="legend-tentative"></i>Tentative</span></div></div><div class="calendar-grid"><div class="calendar-weekdays">${mondayNames.map(name=>`<span>${name}</span>`).join('')}</div><div class="calendar-days">${cells}</div></div><section class="calendar-upcoming"><div class="calendar-section-heading"><div><h3>Holidays this month</h3><p>${visible.length} listed date${visible.length===1?'':'s'}</p></div></div><div class="calendar-holiday-list">${visible.map(holiday=>`<article class="calendar-holiday-row"><span class="calendar-date-tile ${holiday.kind?.toLowerCase()==='tentative'?'tentative':'fixed'}"><b>${Number(holiday.date.slice(8,10))}</b><small>${escapeHtml(new Date(`${holiday.date}T12:00:00`).toLocaleDateString(undefined,{month:'short'}))}</small></span><div class="calendar-holiday-copy"><b>${escapeHtml(holiday.name)}</b><small>${escapeHtml(dateLabel(holiday.date))}${holiday.description?` · ${escapeHtml(holiday.description)}`:''}</small></div><span class="holiday-kind ${holiday.kind?.toLowerCase()==='tentative'?'tentative':'fixed'}">${holiday.kind?.toLowerCase()==='tentative'?'Tentative':'Fixed'}</span>${user.role==='ADMIN'?`<button class="secondary holiday-edit-button" type="button" data-edit-holiday="${holiday.id}">Edit</button><button class="secondary holiday-delete-button" type="button" data-delete-holiday="${holiday.id}">Remove</button>`:''}</article>`).join('')||'<div class="empty-state">No holidays are listed for this month.</div>'}</div></section>`;
  body.querySelector('#calendar-prev').addEventListener('click',()=>renderCalendar(user,shiftCalendarMonth(month,-1)));
  body.querySelector('#calendar-next').addEventListener('click',()=>renderCalendar(user,shiftCalendarMonth(month,1)));
  body.querySelector('#calendar-today').addEventListener('click',()=>renderCalendar(user,localDateString().slice(0,7)));
  const createForm=body.querySelector('#holiday-create-form');
  if(createForm)createForm.addEventListener('submit',async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(createForm));try{await apiRequest('/holidays/',{method:'POST',body:JSON.stringify(data)});showToast(`${data.kind} holiday added to the company calendar.`);await renderCalendar(user,month);}catch(error){showToast(error.message);}});
  body.querySelectorAll('[data-edit-holiday]').forEach(button=>button.addEventListener('click',()=>{
    const holiday=visible.find(item=>Number(item.id)===Number(button.dataset.editHoliday));if(!holiday)return;
    const modal=document.createElement('div');modal.className='modal-backdrop';modal.innerHTML=`<section class="modal" role="dialog" aria-modal="true"><div class="modal-header"><div><span class="eyebrow">COMPANY CALENDAR</span><h2>Edit holiday</h2></div><button type="button" class="icon-btn" data-close-holiday aria-label="Close">×</button></div><form id="holiday-edit-form"><label>Holiday name<input name="name" value="${escapeHtml(holiday.name)}" maxlength="100" required></label><div class="form-row"><label>Date<input name="date" type="date" value="${escapeHtml(holiday.date)}" required></label><label>Status<select name="kind"><option value="Fixed" ${holiday.kind?.toLowerCase()==='fixed'?'selected':''}>Fixed</option><option value="Tentative" ${holiday.kind?.toLowerCase()==='tentative'?'selected':''}>Tentative</option></select></label></div><label>Note<input name="description" value="${escapeHtml(holiday.description||'')}"></label><div class="modal-actions"><button type="button" class="secondary" data-close-holiday>Cancel</button><button type="submit" class="primary">Save holiday</button></div></form></section>`;document.body.append(modal);modal.querySelectorAll('[data-close-holiday]').forEach(control=>control.addEventListener('click',()=>modal.remove()));modal.addEventListener('click',event=>{if(event.target===modal)modal.remove();});modal.querySelector('#holiday-edit-form').addEventListener('submit',async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.currentTarget));try{await apiRequest(`/holidays/${holiday.id}/`,{method:'PATCH',body:JSON.stringify(data)});modal.remove();showToast('Holiday updated.');await renderCalendar(user,month);}catch(error){showToast(error.message);}});
  }));
  body.querySelectorAll('[data-delete-holiday]').forEach(button=>button.addEventListener('click',async()=>{const holiday=visible.find(item=>Number(item.id)===Number(button.dataset.deleteHoliday));if(!holiday||!window.confirm(`Remove ${holiday.name} from the company calendar?`))return;try{await apiRequest(`/holidays/${holiday.id}/`,{method:'DELETE'});showToast('Holiday removed.');await renderCalendar(user,month);}catch(error){showToast(error.message);}}));
}

function shiftCalendarMonth(month,offset) {
  const [year,monthNumber]=month.split('-').map(Number);const target=new Date(year,monthNumber-1+offset,1);return `${target.getFullYear()}-${String(target.getMonth()+1).padStart(2,'0')}`;
}

function renderPeopleTable(employees) {
  const directory=document.querySelector('#people-directory');if(!directory)return;
  const count=document.querySelector('#people-count');if(count)count.textContent=`${employees.length} employee${employees.length===1?'':'s'}`;
  directory.innerHTML=`<div class="people-table-wrap"><table class="people-table"><thead><tr><th>EMPLOYEE</th><th>COMPANY</th><th>DEPARTMENT</th><th>DESIGNATION</th><th>JOINED</th><th>STATUS</th></tr></thead><tbody>${employees.map(employee=>`<tr><td><div class="people-name-cell"><span class="people-avatar">${escapeHtml((employee.first_name||'?').slice(0,1).toUpperCase())}</span><span><b>${escapeHtml(`${employee.first_name||''} ${employee.last_name||''}`.trim()||'Employee')}</b><small>${escapeHtml(employee.code||'')} · ${escapeHtml(employee.user?.email||'')}</small></span></div></td><td>${escapeHtml(employee.company_name||'Not provided')}</td><td>${escapeHtml(employee.department_name||'Unassigned')}</td><td>${escapeHtml(employee.designation||'Not provided')}</td><td>${escapeHtml(dateLabel(employee.joining_date))}</td><td><span class="status ${employee.status==='Active'?'status-green':employee.status==='Terminated'||employee.status==='Resigned'?'status-gray':'status-peach'}">${escapeHtml(employee.status||'Active')}</span></td></tr>`).join('')||'<tr><td colspan="6"><div class="empty-state">No employees match these filters.</div></td></tr>'}</tbody></table></div>`;
}

async function renderAttendance(user) {
  const panel = document.querySelector('.auth-welcome');
  panel.innerHTML = `<div class="panel-head"><div><h2>Attendance</h2><p>${user.role === 'ADMIN' ? 'Set the office geofence and review attendance.' : 'Check in and out from the office attendance area.'}</p></div></div><div id="attendance-panel-body"><p>Loading attendance...</p></div>`;
  try {
    const [settings, records] = await Promise.all([apiRequest('/attendance-settings/'), apiRequest('/attendance/')]);
    if (user.role === 'ADMIN') renderAdminAttendance(settings, records);
    else renderEmployeeAttendance(settings, records);
  } catch (error) {
    document.querySelector('#attendance-panel-body').innerHTML = `<p class="form-error">${escapeHtml(error.message)}</p>`;
  }
}

function renderAdminAttendance(settings, records) {
  const body = document.querySelector('#attendance-panel-body');
  const rows = records.slice(0, 20).map(row => `<tr><td>${escapeHtml(row.employee_name || 'Employee')}</td><td>${escapeHtml(row.date)}</td><td>${punchTime(row.check_in)}</td><td>${punchTime(row.check_out)}</td><td>${escapeHtml(row.status)}</td></tr>`).join('');
  body.innerHTML = `<form id="attendance-settings-form" class="attendance-settings-form">
    <div class="attendance-settings-heading"><div><h3>Office attendance rules</h3><p>Employees can punch only inside this location and radius.</p></div><span class="status ${settings.configured ? 'status-green' : 'status-peach'}">${settings.configured ? 'Location set' : 'Location required'}</span></div>
    <div class="report-form attendance-form-grid">
      <label>Office latitude<input name="office_latitude" type="number" step="0.000001" min="-90" max="90" value="${settings.office_latitude ?? ''}" required></label>
      <label>Office longitude<input name="office_longitude" type="number" step="0.000001" min="-180" max="180" value="${settings.office_longitude ?? ''}" required></label>
      <label>Allowed radius (metres)<input name="radius_meters" type="number" min="25" max="5000" value="${settings.radius_meters}" required></label>
      <label>Office starts at<input name="office_start_time" type="time" value="${settings.office_start_time}" required></label>
      <label>Office end time (reference)<input name="office_end_time" type="time" value="${settings.office_end_time}" required></label>
      <label>Late grace (minutes)<input name="grace_minutes" type="number" min="0" max="120" value="${settings.grace_minutes}" required></label>
    </div>
    <div class="attendance-form-actions"><button type="button" class="secondary" id="use-office-location">Use this device location</button><button class="primary">Save attendance settings</button></div>
  </form>
  <div class="attendance-records"><div class="panel-head"><div><h3>Recent attendance</h3><p>Latest check-in and check-out records.</p></div></div><div class="attendance-table-wrap"><table class="attendance-table"><thead><tr><th>Employee</th><th>Date</th><th>Check in</th><th>Check out</th><th>Status</th></tr></thead><tbody>${rows || '<tr><td colspan="5">No attendance records yet.</td></tr>'}</tbody></table></div></div>`;
  document.querySelector('#use-office-location').addEventListener('click', async () => {
    try {
      const point = await getDeviceLocation();
      document.querySelector('[name="office_latitude"]').value = point.latitude.toFixed(6);
      document.querySelector('[name="office_longitude"]').value = point.longitude.toFixed(6);
      showToast('Office location captured. Save the settings to apply it.');
    } catch (error) { showToast(error.message); }
  });
  document.querySelector('#attendance-settings-form').addEventListener('submit', async event => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    values.radius_meters = Number(values.radius_meters);
    values.grace_minutes = Number(values.grace_minutes);
    try {
      await apiRequest('/attendance-settings/', { method: 'PATCH', body: JSON.stringify(values) });
      showToast('Office attendance settings saved.');
      renderAttendance({ role: 'ADMIN' });
    } catch (error) { showToast(error.message); }
  });
}

function renderEmployeeAttendance(settings, records) {
  const body = document.querySelector('#attendance-panel-body');
  const today = records.find(record => record.date === localDateString());
  const action = !today?.check_in ? 'check_in' : !today.check_out ? 'check_out' : null;
  const configured = settings.configured;
  const buttonText = action === 'check_in' ? 'Check in' : action === 'check_out' ? 'Check out' : 'Attendance complete';
  const historyRows = records.slice(0, 10).map(record => `<tr><td>${escapeHtml(record.date)}</td><td>${punchTime(record.check_in)}</td><td>${punchTime(record.check_out)}</td><td>${escapeHtml(record.status)}</td></tr>`).join('');
  body.innerHTML = `<div class="employee-attendance-card">
    <div class="attendance-today"><div><span class="eyebrow">TODAY</span><h3>${new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</h3><p>${configured ? `Check-in radius: ${settings.radius_meters} metres` : 'Office location has not been set by your administrator yet.'}</p></div><span class="status ${today?.status === 'Late' ? 'status-peach' : today?.check_in ? 'status-green' : 'status-peach'}">${today ? escapeHtml(today.status) : 'Not checked in'}</span></div>
    <div class="attendance-punches"><div><small>Checked in</small><strong>${punchTime(today?.check_in)}</strong></div><div><small>Checked out</small><strong>${punchTime(today?.check_out)}</strong></div><div><small>Office hours</small><strong>${settings.office_start_time} - ${settings.office_end_time}</strong></div></div>
    <p class="attendance-location-note">Turn on device location and allow this browser to access it. Check-in requires your location to be within ${settings.radius_meters} metres of the office. Check-out is available any time, from any location.</p>
    <button id="attendance-punch" class="primary" ${(!configured && action === 'check_in') || !action ? 'disabled' : ''}>${buttonText}</button>
  </div>
  <div class="attendance-records employee-history"><div class="panel-head"><div><h3>Your attendance history</h3><p>Your recent check-in and check-out times.</p></div></div><div class="attendance-table-wrap"><table class="attendance-table"><thead><tr><th>Date</th><th>Check in</th><th>Check out</th><th>Status</th></tr></thead><tbody>${historyRows || '<tr><td colspan="4">No attendance recorded yet.</td></tr>'}</tbody></table></div></div>`;
  const button = document.querySelector('#attendance-punch');
  if (button && action) button.addEventListener('click', async () => {
    button.disabled = true;
    button.textContent = action === 'check_in' ? 'Getting your location...' : 'Checking out...';
    try {
      const point = action === 'check_in' ? await getDeviceLocation() : {};
      await apiRequest('/attendance/', { method: 'POST', body: JSON.stringify({ action, ...point }) });
      showToast(action === 'check_in' ? 'You are checked in.' : 'You are checked out.');
      await renderAttendance({ role: 'EMPLOYEE' });
    } catch (error) {
      showToast(error.message);
      button.disabled = false;
      button.textContent = buttonText;
    }
  });
}


function dateLabel(value) {
  return value ? new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '';
}

function requestDates(start, end) {
  if (!start || !end || end < start) return [];
  const dates=[];
  const cursor=new Date(`${start}T12:00:00`);
  const last=new Date(`${end}T12:00:00`);
  while (cursor<=last) { dates.push(new Date(cursor)); cursor.setDate(cursor.getDate()+1); }
  return dates;
}

async function renderRequests(user, preferredType='Leave') {
  const panel=document.querySelector('.auth-welcome');
  panel.innerHTML=`<div class="panel-head"><div><h2>Leave &amp; WFH</h2><p>${user.role==='ADMIN'?'Review employee leave and work-from-home requests.':'Choose leave or work from home and send your request for approval.'}</p></div></div><div id="requests-panel-body"><p>Loading requests...</p></div>`;
  try {
    const [leaves,wfh,holidays]=await Promise.all([apiRequest('/leave-requests/'),apiRequest('/wfh-requests/'),apiRequest('/holidays/')]);
    if(user.role==='ADMIN') renderAdminRequests(leaves,wfh);
    else renderEmployeeRequests(user,leaves,wfh,holidays,preferredType);
  } catch(error) { document.querySelector('#requests-panel-body').innerHTML=`<p class="form-error">${escapeHtml(error.message)}</p>`; }
}

function requestRow(type,row,admin=false) {
  const isLeave=type==='Leave';
  const reason=escapeHtml(row.reason||'No reason provided');
  const person=admin?`<b>${escapeHtml(row.employee_name||'Employee')}</b>`:'';
  const days=isLeave?`<span class="request-days">${row.total_days} leave day${row.total_days===1?'':'s'}</span>`:'';
  const actions=admin&&row.status==='Pending'?`<div class="request-review-actions"><button class="approve-btn" data-request-type="${type}" data-request-id="${row.id}" data-decision="Approved">Approve</button><button class="reject-btn" data-request-type="${type}" data-request-id="${row.id}" data-decision="Rejected">Reject</button></div>`:'';
  return `<article class="request-card"><div class="request-card-top"><div><span class="request-kind">${type==='WFH'?'Work from home':`${escapeHtml(row.leave_type||'Leave')} leave`}</span>${person}<p>${dateLabel(row.start_date)} - ${dateLabel(row.end_date)}${days?` ? ${days}`:''}</p></div><span class="status ${row.status==='Approved'?'status-green':row.status==='Rejected'?'status-peach':'status-pending'}">${escapeHtml(row.status)}</span></div><p class="request-reason">${reason}</p>${actions}</article>`;
}

function renderAdminRequests(leaves,wfh) {
  const combined=[...leaves.map(row=>({type:'Leave',row})),...wfh.map(row=>({type:'WFH',row}))].sort((a,b)=>new Date(b.row.applied_at)-new Date(a.row.applied_at));
  const pending=combined.filter(item=>item.row.status==='Pending');
  const history=combined.filter(item=>item.row.status!=='Pending');
  const body=document.querySelector('#requests-panel-body');
  body.innerHTML=`<div class="request-section"><div class="panel-head"><div><h3>Waiting for review</h3><p>${pending.length} pending request${pending.length===1?'':'s'}</p></div></div><div class="request-card-list">${pending.map(item=>requestRow(item.type,item.row,true)).join('')||'<div class="empty-state">No requests are waiting for approval.</div>'}</div></div><div class="request-section"><div class="panel-head"><div><h3>Request history</h3><p>Recently reviewed leave and WFH requests.</p></div></div><div class="request-card-list">${history.slice(0,30).map(item=>requestRow(item.type,item.row,true)).join('')||'<div class="empty-state">No reviewed requests yet.</div>'}</div></div>`;
  body.querySelectorAll('[data-decision]').forEach(button=>button.addEventListener('click',async()=>{
    const comment=button.dataset.decision==='Rejected'?(window.prompt('Add a note for the employee (optional)')||''):'';
    const endpoint=button.dataset.requestType==='WFH'?'wfh-requests':'leave-requests';
    try {
      await apiRequest(`/${endpoint}/${button.dataset.requestId}/review/`,{method:'POST',body:JSON.stringify({status:button.dataset.decision,comment})});
      showToast(`${button.dataset.requestType} request ${button.dataset.decision.toLowerCase()}.`);
      renderRequests({role:'ADMIN'});
    } catch(error) { showToast(error.message); }
  }));
}

function renderEmployeeRequests(user,leaves,wfh,holidays,preferredType='Leave') {
  const holidaySet=new Set(holidays.map(item=>item.date));
  const all=[...leaves.map(row=>({type:'Leave',row})),...wfh.map(row=>({type:'WFH',row}))].sort((a,b)=>new Date(b.row.applied_at)-new Date(a.row.applied_at));
  const body=document.querySelector('#requests-panel-body');
  body.innerHTML=`<form id="employee-request-form" class="employee-request-form">
    <div class="request-form-heading"><div><h3>New request</h3><p>Requests are sent to your administrator for approval.</p></div></div>
    <div class="report-form request-fields">
      <label>Request type<select name="request_type" id="request-type"><option value="Leave" ${preferredType==='Leave'?'selected':''}>Leave</option><option value="WFH" ${preferredType==='WFH'?'selected':''}>Work from home (WFH)</option></select></label>
      <label id="leave-type-field">Leave type<select name="leave_type"><option>Casual</option><option>Sick</option><option>Annual</option><option>Unpaid</option></select></label>
      <label>From<input type="date" name="start_date" required></label>
      <label>To<input type="date" name="end_date" required></label>
      <label class="reason-field">Reason<textarea name="reason" rows="3" required placeholder="Tell your administrator why you are requesting this"></textarea></label>
    </div>
    <p id="request-day-estimate" class="request-day-estimate">Choose dates to calculate the leave days requested.</p>
    <div class="attendance-form-actions"><button class="primary">Send request for approval</button></div>
  </form>
  <div class="request-section"><div class="panel-head"><div><h3>My leave and WFH requests</h3><p>Track the status of both types of request here.</p></div></div><div class="request-card-list">${all.map(item=>requestRow(item.type,item.row)).join('')||'<div class="empty-state">You have not sent any requests yet.</div>'}</div></div>`;
  const form=body.querySelector('#employee-request-form');
  const typeField=body.querySelector('#request-type');
  const leaveType=body.querySelector('#leave-type-field');
  const estimate=body.querySelector('#request-day-estimate');
  function updateEstimate() {
    const data=new FormData(form); const dates=requestDates(data.get('start_date'),data.get('end_date'));
    leaveType.hidden=data.get('request_type')!=='Leave';
    if(!dates.length){estimate.textContent='Choose dates to calculate the requested days.';return;}
    if(data.get('request_type')==='Leave') {
      const days=dates.filter(date=>date.getDay()!==0&&date.getDay()!==6&&!holidaySet.has(`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`)).length;
      estimate.textContent=`This request uses ${days} working day${days===1?'':'s'} of leave. Weekends and company holidays are excluded.`;
    } else estimate.textContent=`This WFH request covers ${dates.length} calendar day${dates.length===1?'':'s'}.`;
  }
  typeField.addEventListener('change',updateEstimate);
  form.querySelector('[name="start_date"]').addEventListener('change',updateEstimate);
  form.querySelector('[name="end_date"]').addEventListener('change',updateEstimate);
  updateEstimate();
  form.addEventListener('submit',async event=>{
    event.preventDefault(); const values=Object.fromEntries(new FormData(form));
    if(values.end_date<values.start_date){showToast('The end date must be on or after the start date.');return;}
    const endpoint=values.request_type==='Leave'?'leave-requests':'wfh-requests';
    const payload={start_date:values.start_date,end_date:values.end_date,reason:values.reason.trim()};
    if(values.request_type==='Leave')payload.leave_type=values.leave_type;
    try {
      const created=await apiRequest(`/${endpoint}/`,{method:'POST',body:JSON.stringify(payload)});
      const summary=values.request_type==='Leave'?`${created.total_days} day${created.total_days===1?'':'s'} of leave`:'WFH';
      showToast(`${summary} request sent to your administrator.`);
      await renderRequests(user,preferredType);
    } catch(error) { showToast(error.message); }
  });
}

async function renderNotifications(user) {
  const panel=document.querySelector('.auth-welcome');
  panel.innerHTML=`<div class="panel-head"><div><h2>Notifications</h2><p>${user.role==='ADMIN'?'Post an update for employees and review your notifications.':'Updates from your administrator and request decisions.'}</p></div></div><div id="notifications-panel-body"><p>Loading notifications...</p></div>`;
  try { const items=await apiRequest('/notifications/'); renderNotificationList(user,items); }
  catch(error) { document.querySelector('#notifications-panel-body').innerHTML=`<p class="form-error">${escapeHtml(error.message)}</p>`; }
}

async function renderInbox(user, selectedContactId=null) {
  clearInterval(chatRefreshTimer);
  const panel=document.querySelector('.auth-welcome');
  panel.innerHTML=`<div class="panel-head"><div><h2>Inbox</h2><p>Private messages between employees and administrators.</p></div></div><div id="inbox-body"><p>Loading your inbox...</p></div>`;
  try {
    const [contacts,messages]=await Promise.all([apiRequest('/messages/contacts/'),apiRequest('/messages/')]);
    renderInboxContent(user,contacts,messages,selectedContactId);
  } catch(error) { document.querySelector('#inbox-body').innerHTML=`<p class="form-error">${escapeHtml(error.message)}</p>`; }
}

function renderInboxContent(user,contacts,messages,selectedContactId=null) {
  clearInterval(chatRefreshTimer);
  const body=document.querySelector('#inbox-body');
  if(!contacts.length) { body.innerHTML='<div class="empty-state">No contacts are available yet. Once employee accounts are active, you can start a conversation here.</div>'; return; }
  const recentContactId=messages.length ? (user.id===messages[0].sender ? messages[0].recipient : messages[0].sender) : null;
  const activeId=Number(selectedContactId)||recentContactId||contacts[0].id;
  const active=contacts.find(contact=>Number(contact.id)===Number(activeId))||contacts[0];
  const thread=messages.filter(message=>(Number(message.sender)===Number(user.id)&&Number(message.recipient)===Number(active.id))||(Number(message.recipient)===Number(user.id)&&Number(message.sender)===Number(active.id)));
  thread.filter(message=>Number(message.recipient)===Number(user.id)&&!message.read_at).forEach(message=>apiRequest(`/messages/${message.id}/read/`,{method:'POST',body:'{}'}).catch(()=>{}));
  const summaries=contacts.map(contact=>{
    const last=messages.filter(message=>(Number(message.sender)===Number(user.id)&&Number(message.recipient)===Number(contact.id))||(Number(message.recipient)===Number(user.id)&&Number(message.sender)===Number(contact.id))).at(-1);
    const unread=messages.filter(message=>Number(message.sender)===Number(contact.id)&&Number(message.recipient)===Number(user.id)&&!message.read_at).length;
    return {contact,last,unread};
  }).sort((a,b)=>(b.last?.created_at||'').localeCompare(a.last?.created_at||''));
  body.innerHTML=`<div class="inbox-layout"><aside class="inbox-contacts"><div class="inbox-contacts-heading"><b>Conversations</b><span>${contacts.length}</span></div>${summaries.map(({contact,last,unread})=>`<button type="button" class="inbox-contact ${Number(contact.id)===Number(active.id)?'active':''}" data-contact-id="${contact.id}"><span class="inbox-avatar">${escapeHtml((contact.name||'?').slice(0,1).toUpperCase())}</span><span class="inbox-contact-copy"><b>${escapeHtml(contact.name)}</b><small>${escapeHtml(last?.body||(contact.role==='ADMIN'?'Administrator':'Employee'))}</small></span>${unread?`<i class="inbox-unread">${unread}</i>`:''}</button>`).join('')}</aside><section class="inbox-thread"><header class="inbox-thread-head"><span class="inbox-avatar">${escapeHtml((active.name||'?').slice(0,1).toUpperCase())}</span><div><b>${escapeHtml(active.name)}</b><small>${active.role==='ADMIN'?'Administrator':'Employee'}</small></div></header><div class="inbox-messages" id="inbox-messages">${thread.map(message=>`<article class="chat-bubble ${Number(message.sender)===Number(user.id)?'sent':'received'}"><p>${escapeHtml(message.body)}</p><small>${message.created_at?new Date(message.created_at).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}):''}</small></article>`).join('')||'<div class="empty-state">Start a conversation with a message.</div>'}</div><form class="inbox-compose" id="inbox-compose"><textarea name="body" rows="2" maxlength="5000" required placeholder="Write a message..."></textarea><button class="primary" type="submit">Send</button></form></section></div>`;
  body.querySelectorAll('[data-contact-id]').forEach(button=>button.addEventListener('click',()=>renderInboxContent(user,contacts,messages,button.dataset.contactId)));
  body.querySelector('#inbox-compose').addEventListener('submit',async event=>{
    event.preventDefault();const form=event.currentTarget;const text=new FormData(form).get('body').trim();if(!text)return;
    const submit=form.querySelector('button');submit.disabled=true;
    try { await apiRequest('/messages/',{method:'POST',body:JSON.stringify({recipient:active.id,body:text})});await renderInbox(user,active.id); }
    catch(error) { showToast(error.message);submit.disabled=false; }
  });
  const scroller=body.querySelector('#inbox-messages');scroller.scrollTop=scroller.scrollHeight;
  chatRefreshTimer=setInterval(async()=>{if(document.querySelector('#inbox-body')){try{const latest=await apiRequest('/messages/');renderInboxContent(user,contacts,latest,active.id);}catch{}}},7000);
}

function renderNotificationList(user,items) {
  const body=document.querySelector('#notifications-panel-body');
  const composer=user.role==='ADMIN'?`<form id="announcement-form" class="employee-request-form announcement-form"><div class="request-form-heading"><div><h3>Post an update</h3><p>Employees will receive it in their Notifications.</p></div></div><div class="report-form"><label>Title<input name="title" required maxlength="200"></label><label>Audience<select name="audience"><option value="ALL">All employees</option><option value="EMPLOYEE">Employees</option><option value="ADMIN">Administrators</option></select></label><label class="reason-field">Message<textarea name="message" rows="3" required></textarea></label></div><div class="attendance-form-actions"><button class="primary">Post update</button></div></form>`:'';
  body.innerHTML=`${composer}<div class="notification-list">${items.map(item=>`<article class="notification-card ${item.read_at?'read':'unread'}"><div class="notification-card-top"><div><h3>${escapeHtml(item.title)}</h3><small>${dateLabel(item.created_at?.slice(0,10))} ${item.created_at?new Date(item.created_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}):''}</small></div>${item.read_at?'':'<span class="unread-dot" title="Unread"></span>'}</div><p>${escapeHtml(item.message)}</p>${item.read_at?'':`<button class="text-button" data-read-id="${item.id}">Mark as read</button>`}</article>`).join('')||'<div class="empty-state">You have no notifications yet.</div>'}</div>`;
  const composerForm=body.querySelector('#announcement-form');
  if(composerForm)composerForm.addEventListener('submit',async event=>{
    event.preventDefault(); const data=Object.fromEntries(new FormData(composerForm));
    try { await apiRequest('/announcements/',{method:'POST',body:JSON.stringify(data)}); showToast('Update posted to employee notifications.'); await renderNotifications(user); }
    catch(error) { showToast(error.message); }
  });
  body.querySelectorAll('[data-read-id]').forEach(button=>button.addEventListener('click',async()=>{
    try { await apiRequest(`/notifications/${button.dataset.readId}/read/`,{method:'POST',body:'{}'}); await renderNotifications(user); }
    catch(error) { showToast(error.message); }
  }));
}


async function renderDocuments(user) {
  const panel=document.querySelector('.auth-welcome');
  panel.innerHTML=`<div class="panel-head"><div><h2>My documents</h2><p>Upload and manage your personal employment documents.</p></div></div><div id="documents-panel-body"><p>Loading documents...</p></div>`;
  try { renderDocumentList(await apiRequest('/documents/'),user); }
  catch(error) { document.querySelector('#documents-panel-body').innerHTML=`<p class="form-error">${escapeHtml(error.message)}</p>`; }
}

async function renderPayslips(user) {
  const panel=document.querySelector('.auth-welcome');
  panel.innerHTML=`<div class="panel-head"><div><h2>My payslips</h2><p>Download finalized monthly payslips as PDF files.</p></div></div><div id="payslips-panel-body"><p>Loading payslips...</p></div>`;
  try {
    const payslips=await apiRequest('/payroll/');
    const body=document.querySelector('#payslips-panel-body');
    const money=value=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format(Number(value||0));
    body.innerHTML=payslips.length?`<div class="payslip-list">${payslips.map(pay=>`<article class="payslip-card"><div class="payslip-period"><span class="payslip-icon">PDF</span><div><b>${escapeHtml(new Date(Number(pay.year),Number(pay.month)-1,1).toLocaleDateString(undefined,{month:'long',year:'numeric'}))}</b><small>Finalized payslip</small></div></div><div class="payslip-amount"><small>Net pay</small><b>${escapeHtml(money(pay.net))}</b></div><button type="button" class="primary payslip-download" data-payslip-id="${pay.id}" data-payslip-name="payslip-${pay.year}-${String(pay.month).padStart(2,'0')}.pdf">Download PDF</button></article>`).join('')}</div>`:'<div class="empty-state">No finalized payslips are available yet. Your administrator will publish one after completing payroll.</div>';
    body.querySelectorAll('[data-payslip-id]').forEach(button=>button.addEventListener('click',async()=>{
      button.disabled=true;button.textContent='Preparing PDF...';
      try {
        const response=await fetch(`${API}/payslips/${button.dataset.payslipId}/`,{headers:{Authorization:`Bearer ${localStorage.getItem('epms_access')}`}});
        if(!response.ok){const error=await response.json().catch(()=>({}));throw new Error(error.detail||'Could not download the payslip.');}
        const blob=await response.blob();const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=button.dataset.payslipName||'payslip.pdf';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);showToast('Payslip PDF downloaded.');
      } catch(error) { showToast(error.message); }
      finally { button.disabled=false;button.textContent='Download PDF'; }
    }));
  } catch(error) { document.querySelector('#payslips-panel-body').innerHTML=`<p class="form-error">${escapeHtml(error.message)}</p>`; }
}

async function renderAdminPayroll() {
  const panel=document.querySelector('.auth-welcome');
  const period=localDateString().slice(0,7);
  panel.innerHTML=`<div class="panel-head"><div><h2>Payroll &amp; salary</h2><p>Set monthly salary components, calculate leave deductions, and publish employee payslips.</p></div></div><div id="admin-payroll-body"><p>Loading payroll workspace...</p></div>`;
  try {
    const employees=await apiRequest('/employees/');
    const body=document.querySelector('#admin-payroll-body');
    if(!employees.length){body.innerHTML='<div class="empty-state">Add employees before setting up payroll.</div>';return;}
    body.innerHTML=`<section class="salary-setup-card"><div class="salary-section-heading"><div><h3>Employee salary setup</h3><p>Enter monthly amounts in INR. Changes are saved as effective dated salary history.</p></div><span class="salary-step">1 · SET UP</span></div><form id="salary-setup-form"><div class="salary-fields"><label>Employee<select name="employee" required>${employees.map(employee=>`<option value="${employee.id}">${escapeHtml(`${employee.first_name} ${employee.last_name}`.trim())} · ${escapeHtml(employee.code)}</option>`).join('')}</select></label><label>Effective from<input name="effective_from" type="date" value="${period}-01" required></label><label>Basic salary / month<input name="basic" type="number" min="0" step="0.01" required></label><label>House rent allowance (HRA)<input name="hra" type="number" min="0" step="0.01" value="0"></label><label>Dearness allowance (DA)<input name="da" type="number" min="0" step="0.01" value="0"></label><label>Bonus / month<input name="bonus" type="number" min="0" step="0.01" value="0"></label><label>Overtime rate / hour<input name="overtime_rate" type="number" min="0" step="0.01" value="0"></label><label>Provident fund (PF)<input name="pf" type="number" min="0" step="0.01" value="0"></label><label>Professional tax<input name="professional_tax" type="number" min="0" step="0.01" value="0"></label><label>Income tax withholding<input name="income_tax" type="number" min="0" step="0.01" value="0"></label><label>Other deductions<input name="other_deductions" type="number" min="0" step="0.01" value="0"></label></div><div class="salary-form-actions"><small>Leave types marked Unpaid, LOP, or Loss of Pay and recorded absences reduce basic pay by a working-day rate. Approved paid leave does not reduce pay.</small><button type="submit" class="primary">Save salary setup</button></div></form></section><section class="payroll-run-card"><div class="salary-section-heading"><div><h3>Monthly payroll</h3><p>Generate a reviewable breakdown, then publish finalized payslips to employee accounts.</p></div><span class="salary-step">2 · REVIEW &amp; PUBLISH</span></div><form id="payroll-period-form" class="payroll-period-form"><label>Payroll month<input name="period" type="month" value="${period}" max="${period}" required></label><button type="submit" class="primary">Calculate payroll</button><span class="payroll-period-note">Future months cannot be calculated. Current month calculations include recorded dates through today.</span></form><div id="payroll-results"><p>Loading payroll records...</p></div></section>`;
    const salaryForm=body.querySelector('#salary-setup-form');
    const loadSalary=async()=>{
      const records=await apiRequest(`/salary-structures/?employee=${encodeURIComponent(salaryForm.elements.employee.value)}`);
      const effective=salaryForm.elements.effective_from.value;
      const record=records.find(item=>item.effective_from<=effective);
      for(const key of ['basic','hra','da','bonus','overtime_rate','pf','professional_tax','income_tax','other_deductions'])salaryForm.elements[key].value=record?.[key]??(key==='basic'?'':'0');
    };
    salaryForm.elements.employee.addEventListener('change',()=>loadSalary().catch(error=>showToast(error.message)));
    salaryForm.elements.effective_from.addEventListener('change',()=>loadSalary().catch(error=>showToast(error.message)));
    await loadSalary();
    salaryForm.addEventListener('submit',async event=>{
      event.preventDefault();const data=Object.fromEntries(new FormData(salaryForm));
      try { await apiRequest('/salary-structures/',{method:'POST',body:JSON.stringify(data)});showToast('Salary setup saved with its effective date.');await loadSalary(); }
      catch(error) { showToast(error.message); }
    });
    const periodForm=body.querySelector('#payroll-period-form');
    periodForm.elements.period.addEventListener('change',()=>{salaryForm.elements.effective_from.value=`${periodForm.elements.period.value}-01`;loadSalary().catch(()=>{});});
    const loadPayroll=async()=>{
      const [year,month]=periodForm.elements.period.value.split('-');
      const rows=await apiRequest(`/payroll/?month=${month}&year=${year}`);renderAdminPayrollRows(rows);
    };
    periodForm.addEventListener('submit',async event=>{
      event.preventDefault();const [year,month]=periodForm.elements.period.value.split('-');const button=periodForm.querySelector('button');button.disabled=true;button.textContent='Calculating...';
      try {
        const result=await apiRequest('/payroll/generate/',{method:'POST',body:JSON.stringify({month:Number(month),year:Number(year)})});
        const skipped=result.missing_salary_structure||[];showToast(skipped.length?`Payroll calculated. Salary setup missing for: ${skipped.join(', ')}`:`Payroll calculated for ${result.generated.length} employees.`);await loadPayroll();
      } catch(error) { showToast(error.message); }
      finally { button.disabled=false;button.textContent='Calculate payroll'; }
    });
    await loadPayroll();
  } catch(error) { document.querySelector('#admin-payroll-body').innerHTML=`<p class="form-error">${escapeHtml(error.message)}</p>`; }
}

function renderAdminPayrollRows(rows) {
  const container=document.querySelector('#payroll-results');if(!container)return;
  const money=value=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format(Number(value||0));
  const pending=rows.filter(row=>row.status!=='Finalized').length;
  container.innerHTML=`<div class="payroll-overview-strip"><span><b>${rows.length}</b> employee${rows.length===1?'':'s'}</span><span><b>${pending}</b> awaiting publication</span><span><b>${escapeHtml(money(rows.reduce((sum,row)=>sum+Number(row.net||0),0)))}</b> total take-home</span></div><div class="payroll-table-wrap"><table class="payroll-admin-table"><thead><tr><th>EMPLOYEE</th><th>WORKING DAYS</th><th>APPROVED LEAVE</th><th>GROSS PAY</th><th>LEAVE / ABSENCE</th><th>OTHER DEDUCTIONS</th><th>NET PAY</th><th>STATUS</th><th></th></tr></thead><tbody>${rows.map(row=>`<tr><td><b>${escapeHtml(row.employee_name||'Employee')}</b><small>${escapeHtml(row.employee_code||'')}</small></td><td>${row.present_days} / ${row.working_days}</td><td>${row.leave_days}</td><td>${escapeHtml(money(row.gross))}</td><td>${escapeHtml(money(row.leave_deduction))}</td><td>${escapeHtml(money(Math.max(0,Number(row.deductions)-Number(row.leave_deduction))))}</td><td><b>${escapeHtml(money(row.net))}</b></td><td><span class="status ${row.status==='Finalized'?'status-green':'status-peach'}">${escapeHtml(row.status)}</span></td><td>${row.status==='Finalized'?`<button type="button" class="secondary small payroll-pdf" data-pdf-id="${row.id}" data-pdf-name="payslip-${row.year}-${String(row.month).padStart(2,'0')}.pdf">PDF</button>`:`<button type="button" class="primary small payroll-publish" data-publish-id="${row.id}">Publish</button>`}</td></tr>`).join('')||'<tr><td colspan="9"><div class="empty-state">No payroll records for this month yet. Save salary setups, then calculate payroll.</div></td></tr>'}</tbody></table></div>`;
  container.querySelectorAll('[data-publish-id]').forEach(button=>button.addEventListener('click',async()=>{
    const row=rows.find(item=>Number(item.id)===Number(button.dataset.publishId));if(!row||!window.confirm(`Finalize ${row.employee_name}'s ${new Date(Number(row.year),Number(row.month)-1,1).toLocaleDateString(undefined,{month:'long',year:'numeric'})} payslip and notify them?`))return;
    button.disabled=true;button.textContent='Publishing...';
    try { await apiRequest(`/payroll/${row.id}/finalize/`,{method:'POST',body:'{}'});showToast('Payslip published. The employee has been notified and can download the PDF.');await renderAdminPayroll(); }
    catch(error) { showToast(error.message);button.disabled=false;button.textContent='Publish'; }
  }));
  container.querySelectorAll('[data-pdf-id]').forEach(button=>button.addEventListener('click',async()=>{
    button.disabled=true;try{const response=await fetch(`${API}/payslips/${button.dataset.pdfId}/`,{headers:{Authorization:`Bearer ${localStorage.getItem('epms_access')}`}});if(!response.ok)throw new Error('Could not download this payslip.');const blob=await response.blob();const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=button.dataset.pdfName;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){showToast(error.message);}finally{button.disabled=false;}
  }));
}

function renderDocumentList(documents,user) {
  const body=document.querySelector('#documents-panel-body');
  body.innerHTML=`<form id="employee-document-form" class="employee-request-form document-form"><div class="request-form-heading"><div><h3>Upload a document</h3><p>PDF, PNG or JPG; maximum file size 10 MB.</p></div></div><div class="report-form"><label>Document name<input name="title" required maxlength="150" placeholder="For example, ID proof or certificate"></label><label>Choose file<input name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" required></label></div><div class="attendance-form-actions"><button class="primary">Upload document</button></div></form>
    <div class="request-section"><div class="panel-head"><div><h3>Your documents</h3><p>Files you have submitted to your employee profile.</p></div></div><div class="document-list">${documents.map(item=>`<article class="document-card"><div class="document-file-icon">${escapeHtml((item.file?.split('.').pop()||'FILE').slice(0,4).toUpperCase())}</div><div class="document-card-info"><b>${escapeHtml(item.title)}</b><small>${escapeHtml(item.file?.split('/').pop()||'Uploaded file')} ? Uploaded ${dateLabel(item.uploaded_at?.slice(0,10))}</small></div><span class="status ${item.verified?'status-green':'status-pending'}">${item.verified?'Verified':'Pending review'}</span><div class="document-actions"><button type="button" class="secondary document-download" data-document-id="${item.id}" data-document-name="${escapeHtml(item.file?.split('/').pop()||item.title)}">Download</button><button type="button" class="secondary document-edit" data-edit-document="${item.id}">Edit name</button><button type="button" class="secondary document-remove" data-remove-document="${item.id}">Remove</button></div></article>`).join('')||'<div class="empty-state">You have not uploaded any documents yet.</div>'}</div></div>`;
  body.querySelector('#employee-document-form').addEventListener('submit',async event=>{
    event.preventDefault();const form=event.currentTarget;const values=new FormData(form);const file=values.get('file');
    if(!file||!file.size){showToast('Choose a file to upload.');return;}
    if(file.size>10*1024*1024){showToast('The file must be 10 MB or smaller.');return;}
    if(!['application/pdf','image/png','image/jpeg'].includes(file.type)){showToast('Choose a PDF, PNG or JPG file.');return;}
    try { await apiRequest('/documents/',{method:'POST',body:values});showToast('Document uploaded successfully.');await renderDocuments(user); }
    catch(error) { showToast(error.message); }
  });
  body.querySelectorAll('[data-document-id]').forEach(button=>button.addEventListener('click',async()=>{
    button.disabled=true;button.textContent='Downloading...';
    try {
      const response=await fetch(`${API}/documents/${button.dataset.documentId}/download/`,{headers:{Authorization:`Bearer ${localStorage.getItem('epms_access')}`}});
      if(!response.ok){const error=await response.json().catch(()=>({}));throw new Error(error.detail||'Could not download this document.');}
      const blob=await response.blob();const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=button.dataset.documentName||'employee-document';link.click();URL.revokeObjectURL(url);
    } catch(error) { showToast(error.message); }
    finally { button.disabled=false;button.textContent='Download'; }
  }));
  body.querySelectorAll('[data-edit-document]').forEach(button=>button.addEventListener('click',()=>{
    const item=documents.find(document=>Number(document.id)===Number(button.dataset.editDocument));if(!item)return;
    const backdrop=document.createElement('div');backdrop.className='modal-backdrop';backdrop.innerHTML=`<section class="modal" role="dialog" aria-modal="true" aria-labelledby="edit-document-title"><div class="modal-header"><div><span class="eyebrow">MY DOCUMENTS</span><h2 id="edit-document-title">Edit document name</h2></div><button type="button" class="icon-btn" data-close-modal aria-label="Close">×</button></div><form id="edit-document-form"><label>Document name<input name="title" value="${escapeHtml(item.title)}" maxlength="150" required></label><div class="modal-actions"><button type="button" class="secondary" data-close-modal>Cancel</button><button type="submit" class="primary">Save changes</button></div></form></section>`;
    document.body.append(backdrop);backdrop.querySelectorAll('[data-close-modal]').forEach(control=>control.addEventListener('click',()=>backdrop.remove()));
    backdrop.addEventListener('click',event=>{if(event.target===backdrop)backdrop.remove();});
    backdrop.querySelector('#edit-document-form').addEventListener('submit',async event=>{event.preventDefault();const title=new FormData(event.currentTarget).get('title').trim();if(!title)return;try{await apiRequest(`/documents/${item.id}/`,{method:'PATCH',body:JSON.stringify({title})});backdrop.remove();showToast('Document name updated.');await renderDocuments(user);}catch(error){showToast(error.message);}});
    backdrop.querySelector('input[name="title"]').focus();
  }));
  body.querySelectorAll('[data-remove-document]').forEach(button=>button.addEventListener('click',async()=>{
    const item=documents.find(document=>Number(document.id)===Number(button.dataset.removeDocument));if(!item||!window.confirm(`Remove "${item.title}"? This also deletes the uploaded file.`))return;
    button.disabled=true;try{await apiRequest(`/documents/${item.id}/`,{method:'DELETE'});showToast('Document removed.');await renderDocuments(user);}catch(error){showToast(error.message);button.disabled=false;}
  }));
}

async function renderProfile(user) {
  const panel=document.querySelector('.auth-welcome');
  panel.innerHTML=`<div class="panel-head"><div><h2>My profile</h2><p>Update your company and contact details. Employment information is managed by your administrator.</p></div></div><div id="profile-panel-body"><p>Loading profile...</p></div>`;
  if(!user.employee_id){document.querySelector('#profile-panel-body').innerHTML='<div class="empty-state">No employee profile is linked to this account. Please contact your administrator.</div>';return;}
  try { renderProfileForm(await apiRequest(`/employees/${user.employee_id}/`),user); }
  catch(error) { document.querySelector('#profile-panel-body').innerHTML=`<p class="form-error">${escapeHtml(error.message)}</p>`; }
}

function renderProfileForm(employee,user) {
  const body=document.querySelector('#profile-panel-body');
  const email=employee.user?.email||user.email||'';
  body.innerHTML=`<div class="profile-overview"><div class="profile-overview-avatar">${escapeHtml((employee.first_name||'E').slice(0,1))}${escapeHtml((employee.last_name||'').slice(0,1))}</div><div><h3>${escapeHtml(`${employee.first_name||''} ${employee.last_name||''}`.trim())}</h3><p>${escapeHtml(employee.code||'Employee')} ? ${escapeHtml(employee.designation||'Team member')}</p></div><span class="status ${employee.status==='Active'?'status-green':'status-pending'}">${escapeHtml(employee.status||'Active')}</span></div>
    <form id="employee-profile-form" class="employee-request-form profile-form"><div class="request-form-heading"><div><h3>Personal and company details</h3><p>Your email, department and job details are managed by your administrator.</p></div></div><div class="report-form profile-fields">
      <label>Company name<input value="${escapeHtml(employee.company_name||user.company_name||'')}" disabled></label>
      <label>Work email<input value="${escapeHtml(email)}" disabled></label>
      <label>Phone number<input name="phone" maxlength="20" value="${escapeHtml(employee.phone||'')}" placeholder="Your contact number"></label>
      <label>Emergency contact<input name="emergency_contact" maxlength="20" value="${escapeHtml(employee.emergency_contact||'')}" placeholder="Emergency contact number"></label>
      <label>Department<input value="${escapeHtml(employee.department_name||'Not assigned')}" disabled></label>
      <label>Designation<input value="${escapeHtml(employee.designation||'Not assigned')}" disabled></label>
      <label class="reason-field">Home address<textarea name="address" rows="3" placeholder="Your current address">${escapeHtml(employee.address||'')}</textarea></label>
    </div><div class="attendance-form-actions"><button class="primary">Save profile</button></div></form>`;
  body.querySelector('#employee-profile-form').addEventListener('submit',async event=>{
    event.preventDefault();const values=Object.fromEntries(new FormData(event.currentTarget));
    try { await apiRequest(`/employees/${employee.id}/`,{method:'PATCH',body:JSON.stringify(values)});showToast('Profile details saved.');await renderProfile(user); }
    catch(error) { showToast(error.message); }
  });
}

function showWorkspace(user) {
  if(user.must_change_password){forcePasswordChange(user);return;}
  window.currentUser=user;
  const name = escapeHtml(user.name || 'there');
  const isAdmin = user.role === 'ADMIN';
  const links = isAdmin ? ['Overview', 'People', 'Attendance', 'Calendar', 'Leave & WFH', 'Notifications', 'Inbox', 'Payroll', 'Reports', 'Settings'] : ['Overview', 'Attendance', 'Calendar', 'Leave & WFH', 'Notifications', 'Inbox', 'Documents', 'My payslips', 'My profile'];
  app.innerHTML = `<div class="app-shell"><aside class="sidebar"><div class="side-top"><div class="brand"><div class="brand-mark"><span>h</span></div><div><b>haven</b><small>PEOPLE &amp; PAYROLL</small></div></div></div><div class="workspace-switch"><div class="workspace-icon">N</div><div><b>Northstar Studio</b><small>Workspace</small></div></div><div class="side-label">WORKSPACE</div><nav>${links.map((link, index) => `<button class="nav-link ${index === 0 ? 'active' : ''}" data-tab="${escapeHtml(link)}"><span>${escapeHtml(link.slice(0,1))}</span><span>${escapeHtml(link)}</span></button>`).join('')}</nav><div class="sidebar-bottom"><div class="profile-row"><div class="avatar avatar-blue">${escapeHtml(name.slice(0, 1))}</div><div class="profile-info"><b>${name}</b><small>${isAdmin ? 'Administrator' : 'Employee'}</small></div><button class="secondary signout-btn" id="signout" type="button">Sign out</button></div></div></aside><main class="main-area"><header class="topbar"><div class="breadcrumb">Workspace <span>?</span> <b id="crumb">Overview</b></div><div class="date-chip">${new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</div></header><section class="page-content"><div class="welcome-row"><div><div class="eyebrow">${new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }).toUpperCase()} <span class="live-dot"></span></div><h1 id="welcome">Good morning, ${name}</h1><p class="welcome-sub">${isAdmin ? 'Your people and payroll workspace.' : 'Your workday, in one simple view.'}</p></div></div><section class="panel auth-welcome"><div class="panel-head"><div><h2 id="panel-title">Welcome to Haven</h2><p id="panel-copy">You are signed in securely as ${isAdmin ? 'an administrator' : 'an employee'}.</p></div><div class="report-icon">H</div></div><p>Your workspace is ready. Use the navigation to explore the available sections.</p></section></section></main></div>`;
  document.querySelector('.workspace-switch b').textContent=user.company_name||'Company workspace';
  document.querySelector('.workspace-icon').textContent=(user.company_name||'C').slice(0,1).toUpperCase();
  document.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click', async () => {
    document.querySelectorAll('[data-tab]').forEach(item => item.classList.toggle('active', item === button));
    const tab = button.dataset.tab;
    clearInterval(chatRefreshTimer);
    document.querySelector('#crumb').textContent = tab;
    if (tab === 'People' && isAdmin) { await renderPeople(); return; }
    if (tab === 'Calendar') { await renderCalendar(user); return; }
    if (tab === 'Payroll' && isAdmin) { await renderAdminPayroll(); return; }
    if (tab === 'Inbox') { await renderInbox(user); return; }
    if (tab === 'Attendance') { await renderAttendance(user); return; }
    if (tab === 'Leave & WFH') { await renderRequests(user); return; }
    if (tab === 'Notifications') { await renderNotifications(user); return; }
    if (tab === 'Documents' && user.role !== 'ADMIN') { await renderDocuments(user); return; }
    if (tab === 'My payslips' && user.role !== 'ADMIN') { await renderPayslips(user); return; }
    if (tab === 'My profile' && user.role !== 'ADMIN') { await renderProfile(user); return; }
    const panel = document.querySelector('.auth-welcome');
    panel.innerHTML = `<div class="panel-head"><div><h2 id="panel-title">${escapeHtml(tab === 'Overview' ? 'Welcome to Haven' : tab)}</h2><p id="panel-copy">${tab === 'Overview' ? `You are signed in securely as ${isAdmin ? 'an administrator' : 'an employee'}.` : `${escapeHtml(tab)} workspace`}</p></div><div class="report-icon">H</div></div><p>${tab === 'Overview' ? 'Your workspace is ready. Use the navigation to explore the available sections.' : 'Use the navigation to explore this section.'}</p>`;
  }));
  document.querySelector('#signout').addEventListener('click', async () => {
    const refresh = localStorage.getItem('epms_refresh');
    const access = localStorage.getItem('epms_access');
    if (refresh) {
      try { await fetch(`${API}/auth/logout/`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${access}` }, body: JSON.stringify({ refresh }) }); } catch {}
    }
    localStorage.removeItem('epms_access');
    localStorage.removeItem('epms_refresh');
    selectedRole = 'EMPLOYEE';
    authScreen('login');
  });
}

const savedToken = localStorage.getItem('epms_access');
if (savedToken) {
  fetch(`${API}/auth/me/`, { headers: { Authorization: `Bearer ${savedToken}` } }).then(response => response.ok ? response.json() : Promise.reject()).then(showWorkspace).catch(() => { localStorage.removeItem('epms_access'); localStorage.removeItem('epms_refresh'); authScreen(); });
} else authScreen();
