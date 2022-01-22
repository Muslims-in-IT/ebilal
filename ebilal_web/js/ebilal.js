/* main app that calls ebilal api */
// Get the current config from the ebilal API

var subscribed_mounts=[];
const baseurl = "http://ebilal.local/api/"; 

// Get subscribed mounts
function getSubscribedMounts(mounts) {
  var url = baseurl + "mounts";
  fetch(url) 
    .then(response => response.text())  
  .then(response => {
    const obj = JSON.parse(response);
    subscribed_mounts = obj.mounts;
    document.getElementById('mounts').value = subscribed_mounts;
    console.log(subscribed_mounts);
  })
  .catch((err) => console.log("Can’t access " + url + " response. Blocked by browser?" + err));
}

//Get volume settings
function getVolume() {
  url = baseurl + "volume";
  fetch(url) 
    .then(response => response.text())  
  .then(response => {
    const obj = JSON.parse(response);
    document.getElementById('volume').value = obj.volume;
  })
  .catch((err) => console.log("Can’t access " + url + " response. Blocked by browser?" + err));
}

// Get the current live streams from the ebilal API
function getLiveStreams() {
const casturl = "https://www.livemasjid.com/api/status-json.xsl";
fetch(casturl) 
  .then(response => response.text())  
.then(response => {
  const obj = JSON.parse(response);
  livemounts = obj.icestats.source;
  var boxes = "";
  livemounts.forEach((livemount, i) => 
  { 
    mount_name = livemount.listenurl;
    mount_name = mount_name.split('/')[3];
    boxes += `<div class="box"><div class="media-content"><div class="content"><p>`;
    boxes += "<strong>"+ livemount.server_name + "</strong><br/>";
    boxes += livemount.server_description;
    boxes += `<br>Mount name: `+mount_name;
    boxes += `</p></div><nav class="level is-mobile">
    <div class="level-left">`;
    if (subscribed_mounts.includes(mount_name)) {
      boxes+= `<a class="level-item" aria-label="favorite" onclick="removeMount('`+mount_name+`')"><span class="icon"><i class="fas fa-heart"></i></span>`;
    } else {
      boxes+= `<a class="level-item" aria-label="favorite" onclick="addMount('`+mount_name+`')"><span class="icon"><i class="far fa-heart"></i></span>`;
    }
    boxes += `</a>
      <a class="level-item" aria-label="listen" href=https://`+livemount.server_url+`>
      <span class="icon"><i class="fas fa-external-link-alt"></i></span>
      </a>
    </div>
    </nav>`;
    boxes += "</div></div>";
  });
  document.getElementById('livemounts').innerHTML = boxes;
})
.catch((err) => console.log("Can’t access " + casturl + " response. Blocked by browser?" + err));
}

// Setup tabs on page load
const TABS = [...document.querySelectorAll('#tabs li')];
const CONTENT = [...document.querySelectorAll('#tab-content div')];
const ACTIVE_CLASS = 'is-active';
const NON_ACTIVE_CLASS = 'is-inactive';

function initTabs() {
    TABS.forEach((tab) => {
      tab.addEventListener('click', (e) => {
        let selected = tab.getAttribute('data-tab');
        updateActiveTab(tab);
        updateActiveContent(selected);
      })
    })
}

function updateActiveTab(selected) {
  TABS.forEach((tab) => {
    if (tab && tab.classList.contains(ACTIVE_CLASS)) {
      tab.classList.remove(ACTIVE_CLASS);
      tab.classList.add(NON_ACTIVE_CLASS);
    }
  });
  selected.classList.add(ACTIVE_CLASS);
}

function updateActiveContent(selected) {
  CONTENT.forEach((item) => {
    if (item && item.classList.contains(ACTIVE_CLASS)) {
      item.classList.remove(ACTIVE_CLASS);
      item.classList.add(NON_ACTIVE_CLASS);
    }
    let data = item.getAttribute('data-content');
    if (data === selected) {
      item.classList.add(ACTIVE_CLASS);
      item.classList.remove(NON_ACTIVE_CLASS);
    }
  });
}

//Set mounts using form data
function setTheMounts(form) {
  console.log(form.mounts.value);
  var theMounts = [];
  theMounts = form.mounts.value.split(',');
  setMounts(theMounts);
}

// Set the configured mount using the ebilal API
function setMounts(mounts) {
  url = baseurl + "mounts";
  let mountObject = {mounts: mounts};
  console.log(mountObject);
  fetch(url, {  method: 'POST',   headers: { 'Content-Type': 'application/json' },   body: JSON.stringify(mounts) })
    .then(response => response.text())
  .then(response => {
    const obj = JSON.parse(response);
    if (obj.status === "ok") {
      getSubscribedMounts();
    } else {  // error
      console.log(obj.error);
    }   // error  
  })
  .catch((err) => console.log("Can’t access " + url + " response. Blocked by browser?" + err));
}

// Add a mount to the subscribed mounts
function addMount(mount) {
  var newMounts = subscribed_mounts;
  if (!(subscribed_mounts.includes(mount))){
    newMounts.push(mount);
    setMounts(newMounts);
  }
  console.log(newMounts);
}

// Remove an item from an array
function arrayRemove(arr, value) { 
    
  return arr.filter(function(ele){ 
      return ele != value; 
  });
}

// Remove a mount from the subscribed mounts
function removeMount(mount) {
  var newMounts = arrayRemove(subscribed_mounts, mount);
  setMounts(newMounts);
  console.log(newMounts);
}

//Set volume using form data
function setTheVolume(form) {
  console.log(form.volume.value);
  setVolume(form.volume.value);
}

// Set the volume using the ebilal API
function setVolume(volume) {
  url = baseurl + "volume" + "/?vol=" + volume;
  fetch(url, {  method: 'POST',   headers: { 'Content-Type': 'application/json' }})
    .then(response => response.text())
  .then(response => {
    const obj = JSON.parse(response);
    if (obj.status === "ok") {
      updateVolume();
    } else {  // error
      console.log(obj.error);
    }   // error  
  })
  .catch((err) => console.log("Can’t access " + url + " response. Blocked by browser?" + err));
}

function init() {
  getSubscribedMounts();
  getVolume();
  getLiveStreams();
  initTabs();
}

init();

