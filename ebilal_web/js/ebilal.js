/* main app that calls ebilal api */
// Get the current config from the ebilal API

var favourites=[];
const apiurl = "/api/"; 
var state;
var livemounts;
var txt = document.getElementById('log');

// Get favourites from the ebilal API
function getFavourites() {
  var url = apiurl + "favourites";
  fetch(url) 
    .then(response => response.text())  
  .then(response => {
    const obj = JSON.parse(response);
    favourites = obj.favourites;
    document.getElementById('favourites').value = favourites;
    for (var i = 0; i < favourites.length; i++) {
      document.getElementById('fav_button_'+favourites[i]).classList.remove('far');
      document.getElementById('fav_button_'+favourites[i]).classList.add('fas');
    }
    console.log(favourites);
  })
  .catch((err) => console.log("Cannot access " + url + " response." + err));
}

//Get volume settings
function getVolume() {
  url = apiurl + "volume";
  fetch(url) 
    .then(response => response.text())  
  .then(response => {
    const obj = JSON.parse(response);
    document.getElementById('volume').value = obj.volume;
  })
  .catch((err) => console.log("Cannot access " + url + " response. Blocked by browser?" + err));
}

// Get the player state
function getPlayerState() {
  url = apiurl + "player";
  fetch(url) 
    .then(response => response.text())  
  .then(response => {
    state = JSON.parse(response);
    if (state.status === "playing") {
      document.getElementById('status').textContent = state.status + " " + state.mount;
      document.getElementById('play_button_'+state.mount).classList.remove('fa-play');
      document.getElementById('play_button_'+state.mount).classList.add('fa-stop');
    } else {
      document.getElementById('status').textContent = state.status;
    }
  })
  .catch((err) => console.log("Cannot access " + url + " response. " + err));
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
      boxes+= `<a class="level-item" aria-label="favorite" onclick="toggleFav('`+mount_name+`')"><span class="icon"><i id="fav_button_`+mount_name+`" class="far fa-heart"></i></span>`;
      boxes+= `<a class="level-item" aria-label="favorite" onclick="togglePlay('`+mount_name+`')"><span class="icon"><i id="play_button_`+mount_name+`" class="fa fa-play"></i></span>`;
      boxes += `</a>
        <a class="level-item" aria-label="listen" href=https://`+livemount.server_url+`>
        <span class="icon"><i class="fas fa-external-link-alt"></i></span>
        </a>
      </div>
      </nav>`;
      boxes += "</div></div>";
    });
    document.getElementById('livemounts').innerHTML = boxes;
    return livemounts;
  })
  .catch((err) => console.log("Cannot access " + casturl + " response." + err));
}

// Get log file from the ebilal API
function getLog() {
  url = "/web.log";  
  fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'text/plain'
      }
    })
    .then(response => response.text())
    .then(response => {
      txt.textContent = response;
      txt.scrollTop = txt.scrollHeight;
    })
    .catch((err) => console.log("Cannott access " + url + " response." + err));
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
  console.log(form.favourites.value);
  var theFavs = [];
  theFavs = form.favourites.value.split(',');
  setFavourites(theFavs);
}

// Set the configured mount using the ebilal API
function setFavourites(favourites) {
  url = apiurl + "favourites";
  console.log(JSON.stringify({"favourites":favourites}))
  fetch(url, {  method: 'POST',   headers: { 'Content-Type': 'application/json' },   body: JSON.stringify({"favourites":favourites})})
    .then(response => response.text())
  .then(response => {
    const obj = JSON.parse(response);
    if (obj.status === "ok") {
      getFavourites();
    } else {  // error
      console.log(obj.error);
    }   // error  
  })
  .catch((err) => console.log("Cannot access " + url + " response. Blocked by browser?" + err));
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

//Toggle the favourites
function toggleFav(mount) {
  if (favourites.includes(mount)) {
    removeFav(mount);
    document.getElementById('fav_button_'+mount).classList.remove('fas');
    document.getElementById('fav_button_'+mount).classList.add('far');
  } else {
    addFav(mount);
    document.getElementById('fav_button_'+mount).classList.remove('far');
    document.getElementById('fav_button_'+mount).classList.add('fas');
  }
}

//Toggle play
function togglePlay(mount) {
  if (state.status === "playing") {
    if (state.mount.includes(mount)) {
      stop();
      document.getElementById('play_button_'+mount).classList.remove('fa-stop');
      document.getElementById('play_button_'+mount).classList.add('fa-play');
    }
  } else {
    play(mount);
    document.getElementById('play_button_'+mount).classList.remove('fa-play');
    document.getElementById('play_button_'+mount).classList.add('fa-stop');
  }
}

// Play a mount using the ebilal API
async function play(mount) {
  url = apiurl + "player/play/" + mount;
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  });
  const playerJson = await response.json(); //extract JSON from the http response
  state = playerJson;
  document.getElementById('status').textContent = state.status;
};

// Stop play using the ebilal API
async function stop() {
  url = apiurl + "player/stop";
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  });
  const playerJson = await response.json(); //extract JSON from the http response
  state = playerJson;
  document.getElementById('status').textContent = state.status;
};

//Set volume using form data
function setTheVolume(form) {
  setVolume(form.volume.value);
}

// Set the volume using the ebilal API
async function setVolume(volume) {
  url = apiurl + "volume" + "?volume=" + volume;
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
  getLiveStreams();
  getFavourites();
  getVolume();
  getPlayerState();
  initTabs();
}

init();

//Poll the ebilal API for the player state
setInterval(function(){
  getLog();
  getPlayerState();
  getLiveStreams();
  getFavourites();
  },30000);

