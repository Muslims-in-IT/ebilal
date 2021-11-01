/* main app that calls ebilal api */
const url = "http://ebilal.local:8000/mounts"; 
fetch(url) 
  .then(response => response.text())  
.then(html => {
  // console.log(html);
  document.getElementById('mounts').innerHTML = html;
})
.catch((err) => console.log("Can’t access " + url + " response. Blocked by browser?" + err));
