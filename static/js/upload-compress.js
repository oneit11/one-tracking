/*
 * Client-side image compression before upload.
 * Phone photos are often 5-12MB each; uploading several over mobile data is slow
 * and can time out ("the page hangs"). This resizes images to a sane max
 * dimension and re-encodes them as JPEG before the form is submitted, cutting
 * upload size by ~10x. Videos and non-image files are left untouched.
 */
(function () {
  var MAX_DIM = 1600;   // longest side in px
  var QUALITY = 0.7;    // JPEG quality

  function compressImage(file) {
    return new Promise(function (resolve) {
      // Only real raster images; skip gif (animation) and non-images.
      if (!file || !file.type || file.type.indexOf('image/') !== 0 || file.type === 'image/gif') {
        resolve(file);
        return;
      }
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () {
        URL.revokeObjectURL(url);
        var w = img.naturalWidth || img.width;
        var h = img.naturalHeight || img.height;
        if (!w || !h) { resolve(file); return; }
        if (w > MAX_DIM || h > MAX_DIM) {
          if (w >= h) { h = Math.round(h * MAX_DIM / w); w = MAX_DIM; }
          else { w = Math.round(w * MAX_DIM / h); h = MAX_DIM; }
        }
        try {
          var canvas = document.createElement('canvas');
          canvas.width = w; canvas.height = h;
          canvas.getContext('2d').drawImage(img, 0, 0, w, h);
          canvas.toBlob(function (blob) {
            if (!blob || blob.size >= file.size) { resolve(file); return; }
            var name = (file.name || 'photo').replace(/\.(heic|heif|png|webp|bmp|tiff?)$/i, '.jpg');
            if (!/\.jpe?g$/i.test(name)) { name += '.jpg'; }
            try {
              resolve(new File([blob], name, { type: 'image/jpeg', lastModified: Date.now() }));
            } catch (e) {
              blob.name = name; resolve(blob);
            }
          }, 'image/jpeg', QUALITY);
        } catch (e) { resolve(file); }
      };
      img.onerror = function () { URL.revokeObjectURL(url); resolve(file); };
      img.src = url;
    });
  }

  function processInput(input) {
    var files = Array.prototype.slice.call(input.files || []);
    if (!files.length) return Promise.resolve();
    return Promise.all(files.map(compressImage)).then(function (out) {
      try {
        var dt = new DataTransfer();
        out.forEach(function (f) { dt.items.add(f); });
        input.files = dt.files;
      } catch (e) { /* older browser: keep originals */ }
    });
  }

  function relevantInputs(form) {
    return Array.prototype.slice.call(form.querySelectorAll('input[type=file]'))
      .filter(function (i) {
        var a = (i.getAttribute('accept') || '');
        return a.indexOf('image') !== -1 || a === '';
      });
  }

  function init() {
    if (typeof DataTransfer === 'undefined') return; // can't rewrite files list
    document.querySelectorAll('form').forEach(function (form) {
      var inputs = relevantInputs(form);
      if (!inputs.length) return;
      form.addEventListener('submit', function (ev) {
        if (form.__compressDone) return;               // already processed
        var hasImages = inputs.some(function (i) {
          return Array.prototype.some.call(i.files || [], function (f) {
            return f.type && f.type.indexOf('image/') === 0;
          });
        });
        if (!hasImages) return;                         // nothing to compress
        ev.preventDefault();
        var btn = form.querySelector('button[type=submit], input[type=submit], button:not([type])');
        var oldHtml;
        if (btn) { oldHtml = btn.innerHTML; btn.disabled = true; btn.innerHTML = '⏳ جاري تجهيز الصور...'; }
        Promise.all(inputs.map(processInput)).then(function () {
          form.__compressDone = true;
          if (btn) { btn.disabled = false; if (oldHtml) btn.innerHTML = oldHtml; }
          if (typeof form.requestSubmit === 'function') form.requestSubmit(); else form.submit();
        });
      });
    });
  }

  if (document.readyState !== 'loading') init();
  else document.addEventListener('DOMContentLoaded', init);
})();
