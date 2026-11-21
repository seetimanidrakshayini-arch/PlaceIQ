/* PlaceIQ – API client. Every page talks to the Flask backend through these helpers. */
async function api(method, url, body, isForm) {
  var opt = { method: method, headers: {}, credentials: "same-origin" };
  if (body !== undefined) {
    if (isForm) { opt.body = body; }
    else { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  }
  var res;
  try { res = await fetch(url, opt); }
  catch (e) { throw new Error("Cannot reach the server. Make sure the Flask app is running."); }
  var data = null;
  try { data = await res.json(); } catch (e) { /* non-JSON */ }
  if (!res.ok || !data || data.ok === false) {
    var er = new Error((data && data.error) || ("Request failed (" + res.status + ")"));
    er.status = res.status;
    if (res.status === 401 && window.sess) { window.sess = null; toast("Session expired. Please log in again."); go("login"); }
    throw er;
  }
  return data;
}
var GET = function (u) { return api("GET", u); };
var POST = function (u, b) { return api("POST", u, b === undefined ? {} : b); };
var PUT = function (u, b) { return api("PUT", u, b); };
var DEL = function (u) { return api("DELETE", u); };

/* Run an async action from a button: shows errors as toasts, optional success toast + re-render. */
async function act(fn, okMsg, refresh) {
  try {
    var r = await fn();
    if (okMsg !== false) toast(okMsg || (r && r.message) || "Done");
    if (refresh !== false) route();
    return r;
  } catch (e) { toast(e.message); return null; }
}
