/* main app that calls ebilal api */
const baseurl = "http://ebilal.local:8000/"; 
fetch(baseurl+"mounts") 
  .then(response => response.text())  
.then(response => {
  const obj = JSON.parse(response);
  document.getElementById('mounts').value = obj.mounts;
})
.catch((err) => console.log("Can’t access " + url + " response. Blocked by browser?" + err));

fetch(baseurl+"volume") 
  .then(response => response.text())  
.then(response => {
  const obj = JSON.parse(response);
  document.getElementById('volume').value = obj.volume;
})
.catch((err) => console.log("Can’t access " + url + " response. Blocked by browser?" + err));
