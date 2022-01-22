/* main app that calls ebilal api */
var subscribed_mounts="";
const baseurl = "http://ebilal.local:8000/"; 
var url = baseurl + "mounts";
fetch(url) 
  .then(response => response.text())  
.then(response => {
  const obj = JSON.parse(response);
  subscribed_mounts = obj.mounts;
  document.getElementById('mounts').value = subscribed_mounts;
})
.catch((err) => console.log("Can’t access " + url + " response. Blocked by browser?" + err));

url = baseurl + "volume";
fetch(url) 
  .then(response => response.text())  
.then(response => {
  const obj = JSON.parse(response);
  document.getElementById('volume').value = obj.volume;
})
.catch((err) => console.log("Can’t access " + url + " response. Blocked by browser?" + err));

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
    <div class="level-left">
      <a class="level-item" aria-label="favorite">`;
    if (subscribed_mounts.includes(mount_name)) {
      boxes+= `<span class="icon"><i class="fas fa-heart"></i></span>`;
    } else {
      boxes+= `<span class="icon"><i class="far fa-heart"></i></span>`;
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

initTabs();

