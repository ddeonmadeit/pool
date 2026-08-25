"""JS for the Mail List page: two value-band dropdowns over the mail-ready set.

Each dropdown is populated from its own embedded JSON array (already
deduplicated by address and sorted best-score-first in build_site.py), so
this script only has to render options and a detail readout for whichever
job is selected.
"""

JS = r"""
(function () {
  "use strict";
  var A=0,SUB=1,PC=2,VAL=3,CD=4,YR=5,SC=6,LAT=7,LON=8,CT=9;
  var COND = [
    ["Green water","c0"],["Original look","c1"],["Redone pre-2005","c2"],
    ["Mid tone","c3"],["Modern dark","c4"],["Unconfirmed","c5"],["Gone","c6"]
  ];
  var THIS_YEAR = new Date().getFullYear();

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function fmtMoney(n) {
    if (n >= 1000000) return "$" + (n / 1000000).toFixed(n % 1000000 === 0 ? 0 : 1) + "M";
    return "$" + Math.round(n / 1000) + "K";
  }

  function band(id, dataId, countId, detailId) {
    var raw = document.getElementById(dataId).textContent;
    var rows = raw ? JSON.parse(raw) : [];
    var sel = document.getElementById(id);
    var detail = document.getElementById(detailId);

    document.getElementById(countId).textContent =
      rows.length.toLocaleString() + (rows.length === 1 ? " property" : " properties");

    // The address string already ends with the suburb name (NSW format), so
    // the option label only adds postcode and value, not the suburb again.
    var opts = '<option value="">Choose an address&hellip;</option>';
    for (var i = 0; i < rows.length; i++) {
      var d = rows[i];
      opts += '<option value="' + i + '">' + esc(d[A]) +
        (d[PC] ? ' ' + esc(d[PC]) : '') + ' — ' + fmtMoney(d[VAL]) + '</option>';
    }
    sel.innerHTML = opts;

    function render() {
      var i = sel.value;
      if (i === "") {
        detail.innerHTML = '<div class="empty">Pick an address above to see its details.</div>';
        return;
      }
      var d = rows[+i];
      var cd = COND[d[CD]] || COND[5];
      var age = d[YR] ? (THIS_YEAR - d[YR]) : null;
      var contact = d[CT] ? '<div class="jobrow">' + d[CT] + '</div>' : '';
      detail.innerHTML =
        '<span class="addr">' + esc(d[A]) + '</span>' +
        '<div class="jobrow">' +
          '<span>' + esc(d[SUB]) + (d[PC] ? ' ' + esc(d[PC]) : '') + '</span>' +
          '<span class="val">' + fmtMoney(d[VAL]) + '</span>' +
          '<span class="pill ' + cd[1] + '">' + cd[0] + '</span>' +
          (age ? '<span>Pool built before ' + d[YR] + ' &middot; ' + age + '+ yr</span>' : '') +
          '<span>Score ' + d[SC] + '</span>' +
          '<a class="maplink" target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query=' +
            d[LAT] + ',' + d[LON] + '">map</a>' +
        '</div>' + contact;
    }
    sel.addEventListener("change", render);
    render();

    return rows;
  }

  var rowsHi = band("band-8m", "jobs-8m", "count-8m", "detail-8m");
  var rowsMid = band("band-4-8m", "jobs-4-8m", "count-4-8m", "detail-4-8m");

  function wireCopy(btnId, rows) {
    document.getElementById(btnId).addEventListener("click", function () {
      var lines = rows.map(function (d) {
        return d[A] + ", " + d[SUB] + " NSW" + (d[PC] ? " " + d[PC] : "");
      });
      var btn = this;
      navigator.clipboard.writeText(lines.join("\n")).then(function () {
        var was = btn.textContent;
        btn.textContent = "Copied " + rows.length;
        setTimeout(function () { btn.textContent = was; }, 1800);
      });
    });
  }
  wireCopy("copy-8m", rowsHi);
  wireCopy("copy-4-8m", rowsMid);
})();
"""
