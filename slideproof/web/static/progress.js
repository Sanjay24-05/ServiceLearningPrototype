(function () {
  var script = document.currentScript;
  var url = script.getAttribute("data-status-url");
  var status = document.getElementById("status");
  var lastShown = status.textContent;
  var lastUpdate = Date.now();
  var timer;

  function fail(message) {
    clearInterval(timer);
    var p = document.createElement("p");
    p.setAttribute("role", "alert");
    p.textContent = message;
    var a = document.createElement("a");
    a.href = "/";
    a.textContent = "Check another file";
    var q = document.createElement("p");
    q.appendChild(a);
    status.parentNode.insertBefore(p, status.nextSibling);
    p.parentNode.insertBefore(q, p.nextSibling);
  }

  function poll() {
    fetch(url).then(function (r) { return r.json(); }).then(function (s) {
      if (s.state === "done") {
        clearInterval(timer);
        location.replace(s.next);
      } else if (s.state === "error") {
        fail(s.message);
      } else if (s.message !== lastShown && Date.now() - lastUpdate >= 3000) {
        status.textContent = s.message;
        lastShown = s.message;
        lastUpdate = Date.now();
      }
    }).catch(function () {});
  }
  timer = setInterval(poll, 1500);
})();
