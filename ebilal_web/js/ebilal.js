/* main app that calls ebilal api */
// Get the current config from the ebilal API

var favourites=[];
const baseurl = "http://ebilal.local/api/"; 

// Get favourites from the ebilal API
function getFavourites() {
  var url = baseurl + "favourites";
  fetch(url) 
    .then(response => response.text())  
  .then(response => {
    const obj = JSON.parse(response);
    favourites = obj.favourites;
    document.getElementById('favourites').value = favourites;
    console.log(favourites);
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
    if (favourites.includes(mount_name)) {
      boxes+= `<a class="level-item" aria-label="favorite" onclick="removeFav('`+mount_name+`')"><span class="icon"><i class="fas fa-heart"></i></span>`;
    } else {
      boxes+= `<a class="level-item" aria-label="favorite" onclick="addFav('`+mount_name+`')"><span class="icon"><i class="far fa-heart"></i></span>`;
    }
    boxes+= `<a class="level-item" aria-label="favorite" onclick="play('`+mount_name+`')"><span class="icon"><i class="far fa-play"></i></span>`;
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
.catch((err) => console.log("Can’t access " + casturl + " response." + err));
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
function setTheFavs(form) {
  console.log(form.mounts.value);
  var theFavs = [];
  theFavs = form.mounts.value.split(',');
  setFavourites(theFavs);
}

// Set the configured mount using the ebilal API
function setFavourites(favourites) {
  url = baseurl + "favourites";
  let favObject = {favourites: favourites};
  console.log(favObject);
  fetch(url, {  method: 'POST',   headers: { 'Content-Type': 'text/plain' },   body: JSON.stringify(favourites) })
    .then(response => response.text())
  .then(response => {
    const obj = JSON.parse(response);
    if (obj.status === "ok") {
      getFavourites();
    } else {  // error
      console.log(obj.error);
    }   // error  
  })
  .catch((err) => console.log("Can’t access " + url + " response. Blocked by browser?" + err));
}

// Add a mount to the subscribed mounts
function addFav(mount) {
  var newFavs = favourites;
  if (!(favourites.includes(mount))){
    newFavs.push(mount);
    setFavourites(newFavs);
  }
  console.log(newFavs);
}

// Remove an item from an array
function arrayRemove(arr, value) { 
    
  return arr.filter(function(ele){ 
      return ele != value; 
  });
}

// Remove a mount from the subscribed mounts
function removeFav(mount) {
  var newFavs = arrayRemove(favourites, mount);
  setFavourites(newFavs);
  console.log(newFavs);
}

// Play a mount using the ebilal API
async function play(mount) {
  url = baseurl + "play";
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  });
  const playerJson = await response.json(); //extract JSON from the http response
  document.getElementById('status').textContent = playerJson.status;
};

//Set volume using form data
function setTheVolume(form) {
  setVolume(form.volume.value);
}

// Set the volume using the ebilal API
async function setVolume(volume) {
  url = baseurl + "volume" + "?vol=" + volume;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  });
  const volJson = await response.json(); //extract JSON from the http response
  document.getElementById('volume').value = volJson.volume;
};

function init() {
  getFavourites();
  getVolume();
  getLiveStreams();
  initTabs();
}

init();

