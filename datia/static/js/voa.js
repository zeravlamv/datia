;(function(){
  function getLang(){
    try{
      if(typeof APP_LANG!=='undefined'&&APP_LANG) return String(APP_LANG);
    }catch(_){}
    var d=document.documentElement;
    return (d&&d.lang)||'es';
  }
  function pickVoice(lang){
    try{
      var voices=window.speechSynthesis.getVoices()||[];
      var lc=(lang||'es').toLowerCase();
      var byLang=voices.filter(function(v){return v&&v.lang&&v.lang.toLowerCase().slice(0,2)===lc.slice(0,2);});
      if(byLang.length>0) return byLang[0];
      var es=voices.filter(function(v){return v&&v.lang&&v.lang.toLowerCase().slice(0,2)==='es';});
      if(es.length>0) return es[0];
      return voices[0]||null;
    }catch(_){return null;}
  }
  function speak(text,lang){
    try{
      if(!('speechSynthesis' in window)) throw new Error('no-tts');
      window.speechSynthesis.cancel();
      var u=new SpeechSynthesisUtterance(String(text||''));
      var v=pickVoice(lang||getLang());
      if(v){u.voice=v;u.lang=v.lang;}
      else{u.lang=(lang||'es-ES');}
      window.speechSynthesis.speak(u);
    }catch(_){
      try{
        var C=window.AudioContext||window.webkitAudioContext;
        if(!C) return;
        var ctx=new C();
        var o=ctx.createOscillator();
        var g=ctx.createGain();
        o.type='sine';
        o.frequency.value=880;
        g.gain.setValueAtTime(0.0001,ctx.currentTime);
        g.gain.exponentialRampToValueAtTime(0.2,ctx.currentTime+0.01);
        g.gain.exponentialRampToValueAtTime(0.0001,ctx.currentTime+0.2);
        o.connect(g);g.connect(ctx.destination);
        o.start();o.stop(ctx.currentTime+0.25);
      }catch(__){}
    }
  }
  function enabled(){
    try{
      return localStorage.getItem('datia-voice-notify')==='true';
    }catch(_){return false;}
  }
  function notify(kind,opts){
    if(!enabled()) return;
    var msg;
    try{
      if(typeof gettext==='function'){msg=gettext('El análisis con inteligencia artificial ha sido completado');}
    }catch(_){}
    if(!msg) msg='El análisis con inteligencia artificial ha sido completado';
    speak(msg,getLang());
  }
  window.VOA={enabled:enabled,getLang:getLang,notify:notify,speak:speak};
})(); 
