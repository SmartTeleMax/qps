function request() {
  res = null;
  if (typeof XMLHttpRequest!="undefined") {
    res = new XMLHttpRequest();
  } else {
    try {
      res = new ActiveXObject("Msxml2.XMLHTTP")
    } catch(e) {
      try {
        res = new ActiveXObject("Microsoft.XMLHTTP")
      } catch(oc) {}
    }
  }
  return res;
}
