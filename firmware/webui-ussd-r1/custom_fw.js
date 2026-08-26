/* MF885 Community WebUI USSD 0.0-ussd-r1 — transport intentionally absent */
(function(w){
  'use strict';
  function install($){
    if(!$||!$.fn)return;
    $.fn.objCustom_FW=function(){
      var root=w.document.getElementById('Content');
      if(!root)throw new Error('USSD content root is missing');
      root.innerHTML=w.callProductHTML('html/home_network/custom_fw_rules.html');
      this.onLoad=function(){};this.onPost=function(){};this.onPostSuccess=function(){};this.setXMLName=function(){};
      return this;
    };
  }
  w.MF885_USSD_R1=Object.freeze({id:'0.0-ussd-r1',contractConfirmed:false,postCapable:false,reason:'Native WebUI endpoint and schema are not proven.'});
  install(w.jQuery);
})(window);
