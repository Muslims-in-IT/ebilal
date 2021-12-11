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
    console.log(mount_name);
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

