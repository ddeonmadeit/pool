"""JS for the Mail List page: two value-band lists over the mail-ready set.

Each band is populated from its own embedded JSON array (already deduplicated
by address and sorted best-score-first in build_site.py), so this script only
has to render the list and wire the copy-all-addresses button per band.
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

  function band(dataId, countId, listId) {
    var raw = document.getElementById(dataId).textContent;
    var rows = raw ? JSON.parse(raw) : [];
    var list = document.getElementById(listId);

    document.getElementById(countId).textContent =
      rows.length.toLocaleString() + (rows.length === 1 ? " property" : " properties");

    if (!rows.length) {
      list.innerHTML = '<div class="empty">No properties in this band.</div>';
      return rows;
    }

    var html = "";
    for (var i = 0; i < rows.length; i++) {
      var d = rows[i];
      var cd = COND[d[CD]] || COND[5];
      var age = d[YR] ? (THIS_YEAR - d[YR]) : null;
      var contact = d[CT] ? '<span>' + d[CT] + '</span>' : '';
      html += '<div class="jobitem">' +
        '<span class="addr">' + esc(d[A]) + '</span>' +
        '<div class="jobrow">' +
          '<span>' + esc(d[SUB]) + (d[PC] ? ' ' + esc(d[PC]) : '') + '</span>' +
          '<span class="val">' + fmtMoney(d[VAL]) + '</span>' +
          '<span class="pill ' + cd[1] + '">' + cd[0] + '</span>' +
          (age ? '<span>Pool built before ' + d[YR] + ' &middot; ' + age + '+ yr</span>' : '') +
          '<span>Score ' + d[SC] + '</span>' +
          '<a class="maplink" target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query=' +
            d[LAT] + ',' + d[LON] + '">map</a>' +
          contact +
        '</div></div>';
    }
    list.innerHTML = html;

    return rows;
  }

  var rowsHi = band("jobs-8m", "count-8m", "list-8m");
  var rowsMid = band("jobs-4-8m", "count-4-8m", "list-4-8m");

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
