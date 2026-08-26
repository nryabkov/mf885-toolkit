/* MF885 Community R2 tab-scoped Digest session 0.2-community-r2 */
(function (w) {
  var KEY = "mf885.community.r2.tab-auth.v1";
  var MAX_IDLE_MS = 600000;
  var activeHA1 = "";
  var activeExpires = 0;
  var restoreAttempted = false;
  var expiryTimer = 0;

  function origin() {
    return w.location.protocol + "//" + w.location.host;
  }

  function storage() {
    try {
      if (!w.sessionStorage || !w.JSON) return null;
      return w.sessionStorage;
    } catch (error) {
      return null;
    }
  }

  function removeStored() {
    var value = storage();
    if (value) {
      try { value.removeItem(KEY); } catch (error) {}
    }
  }

  function forget() {
    activeHA1 = "";
    activeExpires = 0;
    if (expiryTimer) {
      w.clearTimeout(expiryTimer);
      expiryTimer = 0;
    }
    removeStored();
  }

  function expireSession() {
    expiryTimer = 0;
    if (typeof w.clearAuthheader === "function") w.clearAuthheader();
    else forget();
  }

  function scheduleExpiry(expires) {
    var nextTimer = w.setTimeout(expireSession, Math.max(0, expires - new Date().getTime()));
    if (expiryTimer) w.clearTimeout(expiryTimer);
    expiryTimer = nextTimer;
  }

  function readStored() {
    var value = storage();
    var parsed;
    if (!value) return null;
    try {
      parsed = w.JSON.parse(value.getItem(KEY) || "null");
    } catch (error) {
      parsed = null;
    }
    if (!parsed || parsed.v !== 1 || parsed.origin !== origin() ||
        parsed.username !== "admin" || typeof parsed.realm !== "string" ||
        !/^[0-9a-f]{32}$/.test(parsed.ha1 || "") ||
        typeof parsed.expires !== "number" || parsed.expires <= new Date().getTime()) {
      removeStored();
      return null;
    }
    return parsed;
  }

  function writeStored(usernameValue, realm, ha1) {
    var value = storage();
    var expires = new Date().getTime() + MAX_IDLE_MS;
    if (!value) return false;
    try {
      value.setItem(KEY, w.JSON.stringify({
        v: 1,
        origin: origin(),
        username: usernameValue,
        realm: realm,
        ha1: ha1,
        expires: expires
      }));
      scheduleExpiry(expires);
      activeExpires = expires;
      return true;
    } catch (error) {
      removeStored();
      return false;
    }
  }

  function touch() {
    if (activeHA1 && activeExpires && activeExpires <= new Date().getTime()) {
      if (typeof w.clearAuthheader === "function") w.clearAuthheader();
      else forget();
      return;
    }
    var saved = readStored();
    if (saved && activeHA1 === saved.ha1) {
      writeStored(saved.username, saved.realm, saved.ha1);
    }
  }

  function bindActivity() {
    var target = w.document;
    var events = ["mousedown", "keydown", "touchstart"];
    var index;
    if (!target) return;
    if (target.addEventListener) {
      for (index = 0; index < events.length; index++)
        target.addEventListener(events[index], touch, false);
    } else if (target.attachEvent) {
      for (index = 0; index < events.length; index++)
        target.attachEvent("on" + events[index], touch);
    }
  }

  function parseChallenge(value) {
    var parts;
    if (typeof value !== "string") return null;
    parts = value.split(" ");
    if (parts.length < 4 || parts[0] !== "Digest") return null;
    try {
      return {
        realm: getValue(parts[1]),
        nonce: getValue(parts[2]),
        qop: getValue(parts[3])
      };
    } catch (error) {
      return null;
    }
  }

  function statusReadIsExact() {
    var request;
    var xml;
    try {
      request = w.jQuery.ajax({
        type: "GET",
        url: origin() + "/xml_action.cgi?method=get&module=duster&file=status1",
        dataType: "xml",
        async: false,
        cache: false,
        beforeSend: function (xhr) {
          xhr.setRequestHeader("Authorization", getAuthHeader("GET"));
          xhr.setRequestHeader("Cache-Control", "no-store, no-cache, must-revalidate");
        }
      });
      xml = request.responseXML;
    } catch (error) {
      return false;
    }
    if (!xml || !xml.documentElement ||
        String(xml.documentElement.nodeName).toUpperCase() !== "RGW") return false;
    if (w.jQuery(xml).find("login_status").text()) return false;
    return w.jQuery(xml).find("sysinfo hardware_version").text() === "MF96 Ver.D" &&
      w.jQuery(xml).find("sysinfo version_num").text() ===
        "2.5.94_release_MF855_NZ_CP_2.129.003";
  }

  function completeDigestLogin(saved) {
    var challenge = parseChallenge(getAuthType(origin() + "/login.cgi"));
    var rand;
    var salt;
    var cnonce;
    var digest;
    var url;
    if (!challenge || challenge.realm !== saved.realm || challenge.qop !== "auth") return false;
    username = saved.username;
    passwd = "";
    Authrealm = challenge.realm;
    nonce = challenge.nonce;
    Gnonce = nonce;
    AuthQop = challenge.qop;
    GnCount = 1;
    activeHA1 = saved.ha1;
    activeExpires = saved.expires;
    rand = Math.floor(Math.random() * 100001);
    salt = rand + "" + new Date().getTime();
    cnonce = hex_md5(salt).substring(0, 16);
    digest = hex_md5(saved.ha1 + ":" + nonce + ":00000001:" + cnonce +
      ":" + AuthQop + ":" + hex_md5("GET:/cgi/protected.cgi"));
    url = origin() + "/login.cgi?Action=Digest&username=" + username +
      "&realm=" + Authrealm + "&nonce=" + nonce + "&response=" + digest +
      "&qop=" + AuthQop + "&cnonce=" + cnonce + "&temp=marvell";
    return login_done(authentication(url)) && statusReadIsExact();
  }

  function afterManualLogin(remember) {
    var ha1 = hex_md5(username + ":" + Authrealm + ":" + passwd);
    forget();
    activeHA1 = ha1;
    passwd = "";
    if (!statusReadIsExact()) {
      activeHA1 = "";
      return false;
    }
    if (remember) writeStored(username, Authrealm, ha1);
    return true;
  }

  function currentHA1() {
    if (activeHA1 && activeExpires && activeExpires <= new Date().getTime()) {
      forget();
      return "";
    }
    return activeHA1;
  }

  function resume() {
    var saved;
    if (restoreAttempted) return false;
    restoreAttempted = true;
    try {
      saved = readStored();
      if (!saved || !completeDigestLogin(saved)) {
        forget();
        return false;
      }
    } catch (error) {
      forget();
      return false;
    }
    if (!writeStored(saved.username, saved.realm, saved.ha1)) {
      forget();
      return false;
    }
    return true;
  }

  function openAdmin() {
    clearInterval(_zstimeSettingsIntervalID);
    document.getElementById("divAdminApp").innerHTML = callProductHTML("html/adminApp.html");
    document.getElementById("lableWelcome").innerHTML = jQuery.i18n.prop("lableWelcome");
    document.getElementById("quickSetup").innerHTML = jQuery.i18n.prop("quickSetupName");
    document.getElementById("MainHelp").innerHTML = jQuery.i18n.prop("helpName");
    document.getElementById("MainLogOut").innerHTML = jQuery.i18n.prop("LogOutName");
    if (getHardware_Version() === "Ver.B" || getHardware_Version() === "Ver.C")
      jQuery("#lvhomepage").hide();
    else
      jQuery("#lvhomepage").show();
    document.getElementById("lvhomepage").innerHTML = jQuery.i18n.prop("lvhomepage");
    jQuery("#zmlogo").attr("src", zml);
    document.getElementById("divAdminApp").className = "";
    document.getElementsByTagName("body")[0].className = "";
    initAPP();
  }

  function supported() {
    return storage() !== null;
  }

  var stockClearAuthheader = w.clearAuthheader;
  var stockAuthTimeout = w.AuthTimeout;
  var stockAuthKickoff = w.AuthKickoff;
  var stockAuthUnAuth = w.AuthUnAuth;
  w.clearAuthheader = function () { forget(); return stockClearAuthheader(); };
  w.AuthTimeout = function () { forget(); return stockAuthTimeout(); };
  w.AuthKickoff = function () { forget(); return stockAuthKickoff(); };
  w.AuthUnAuth = function () { forget(); return stockAuthUnAuth(); };

  w.MF885CommunityAuth = {
    id: "0.2-community-r2",
    ha1: currentHA1,
    afterManualLogin: afterManualLogin,
    resume: resume,
    openAdmin: openAdmin,
    forget: forget,
    supported: supported
  };
  bindActivity();
})(window);
