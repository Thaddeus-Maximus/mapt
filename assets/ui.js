window.onload = function() {
	document.getElementById("searchBox").addEventListener("keyup", function(event) {
	    if (event.key === "Enter") {
	        runFindPins();
	    }
	});
  document.getElementById("searchButton").addEventListener("click", runFindPins);
  document.getElementById("detailEdit").addEventListener("click", editActiveDetail);
  document.getElementById("detailSave").addEventListener("click", saveActiveDetail);
  document.getElementById("newPin").addEventListener("click", makeNewPin);
  document.getElementById("detailImageUpload").addEventListener("change", loadNewPinImage)
  runFindPins();
}

function loadSvgToMap(url, map)
{
  try{
    const req=new XMLHttpRequest();
    req.onreadystatechange=function()
    {  
      try{
        if(req.readyState == 4)
        {   if(req.status == 200)
            {
              while (map.firstChild)
                map.removeChild(map.firstChild)
              map.appendChild(req.responseXML.documentElement);
            }
            else
            {   console.log("URL "+url+" not available");
            }
        }
      }catch(e){
        console.log("Error parsing SVG: ", e)
      }
    }
    req.open("POST", url, true);
    req.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    req.send();
  }catch(e){
    console.log("Error loading SVG: ", e)
  }
}

function buildSelectList(options, values) {
  const select = document.createElement("select")
  if (values) {
    for (let i=0; i<options.length; i++) {
      const optionElement = document.createElement("option");

      optionElement.textContent = options[i];
      optionElement.value = values[i]

      select.appendChild(optionElement)
    }
  } else if (Array.isArray(options)) {
    for (let i=0; i<options.length; i++) {
      const optionElement = document.createElement("option");

      optionElement.textContent = options[i];
      optionElement.value = options[i]

      select.appendChild(optionElement)
    }
  } else {
    for (const option in options) {
      const optionElement = document.createElement("option");

      optionElement.textContent = option;
      optionElement.value = options[option]

      select.appendChild(optionElement)
    }
  }
  return select
}

function editActiveDetail(event) {
  document.getElementById("detailEdit").style.display = "none"
  document.getElementById("detailSave").style.display = ""
  document.getElementById("detailImageUpload").style.display = ""

  getPin(document.getElementById("detailPane").dataset.pinId).then((pin) =>{
    const title = document.getElementById("detailTitle")
    const titleEdit = document.createElement("input")
    
    titleEdit.value = title.firstChild.innerHTML
    while (title.firstChild)
      title.removeChild(title.firstChild)

    title.appendChild(titleEdit)

    const table = document.getElementById("detailTable")
    for (let i=0; i<table.children.length; i++) {
      let header = table.children[i].children[0]
      let content = table.children[i].children[1]
      
      if (i == 0) {
        let currentType = content.firstChild.innerHTML
        while (content.firstChild)
          content.removeChild(content.firstChild)

        let selectElement = buildSelectList(Object.keys(TYPES))
        selectElement.value = currentType
        console.log(currentType, Object.keys(TYPES))
        content.appendChild(selectElement)
      } else if (i == 1) {
        let currentParent = content.firstChild.innerHTML
        while (content.firstChild)
          content.removeChild(content.firstChild)

        findAreas().then((areas) => {
          console.log(areas)
          let selectElement = buildSelectList({"<none>": null, ...areas})
          selectElement.value = areas[currentParent]
          content.appendChild(selectElement)
        })
      } else {
        let currentText = content.dataset.raw
        while (content.firstChild)
          content.removeChild(content.firstChild)

        let textarea = document.createElement("textarea")
        textarea.value = currentText
        content.appendChild(textarea)
      }
    }
  })
}

function saveActiveDetail(event) {
  const table = document.getElementById("detailTable")
  const pinId = document.getElementById("detailPane").dataset.pinId
  const image = document.getElementById("detailImage")
  pin = {
    "fields": [],
    "name": document.getElementById("detailTitle").firstChild.value
  }

  for (let i=0; i<table.children.length; i++) {
    let header = table.children[i].children[0]
    let content = table.children[i].children[1]
    
    if (i == 0) {
      pin["type"] = content.firstChild.value
    } else if (i == 1) {
      pin["parent"] = content.firstChild.value
    } else {
      pin.fields[i-2] = content.firstChild.value
    }
  }

  if (image.dataset.modified) {
    const filename = pinId+uploadedImage.name.split(/[. ]+/).pop()
    pin["image"] = filename
    storageRef.child("images/"+filename).put(uploadedImage).then((snapshot) => {
      console.log("Uploaded new image")
    })
  }

  sendPin(pinId, pin).then((result) => {
    openPin(pinId)
  })

  console.log("image url:", image.src)


}

let uploadedImage = null

function loadNewPinImage(event) {
  var image = document.getElementById('detailImage');
  image.src = URL.createObjectURL(event.target.files[0]);
  uploadedImage = event.target.files[0]
  image.dataset.modified = true;
  //image.dataset.imageurl = image.src
};

function populatePin(pin) {
  const table = document.getElementById("detailTable")
  while (table.firstChild)
    table.removeChild(table.firstChild)

  function addContent(key, val) {
    const tr = document.createElement("tr")
    const title   = document.createElement("td")
    const content = document.createElement("td")

    title.appendChild(document.createTextNode(key))
    if (typeof val == "string"){
      content.dataset.raw = val;
      content.innerHTML = marked(val);
    } else {
      content.appendChild(val)
    }

    tr.appendChild(title)
    tr.appendChild(content)
    table.appendChild(tr)
  }
  
  addContent("Type", pin.type)

  const link = document.createElement("a")
  addContent("Located In", link)

  if (pin.parent != null) {
    link.dataset.pinId = pin.parent
    link.addEventListener("click", openPin)
    getPin(pin.parent).then((parentPin) => {
      link.appendChild(document.createTextNode(parentPin.name))
    })
  }

  TYPES[pin.type].fields.forEach((field, i) => {
    addContent(field, pin.fields[i])
  })

  document.getElementById("detailTitle").innerHTML = "<h3>"+pin.name+"</h3>";

  function loadImage(url) {
    const image = document.getElementById("detailImage")
    image.setAttribute("src", url);
    image.dataset.modified = false;
    if (pin.type == AREA_TYPE) {
      document.getElementById("mapImage").setAttribute("src", url);
    }
  }

  if (pin.image)
    storageRef.child('images/'+pin.image).getDownloadURL().then(loadImage)
  else
    loadImage(NULL_IMAGE_URL)
}

function openPin(event) {
  if (event == null) {
    populatePin(DEFAULT_PIN_DATA)
    document.getElementById("detailPane").dataset.pinId = undefined
  }

  else if (typeof event === 'string' || event instanceof String) {
    getPin(event).then(populatePin)
    document.getElementById("detailPane").dataset.pinId = event
  }

  else{
    getPin(event.target.dataset.pinId).then(populatePin)
    document.getElementById("detailPane").dataset.pinId = event.target.dataset.pinId
  }

  document.getElementById("detailEdit").style.display = ""
  document.getElementById("detailSave").style.display = "none"
  document.getElementById("detailImageUpload").style.display = "none"
}

function makeNewPin() {
  openPin(null)
  editActiveDetail()
}

function runFindPins() {
  const keyword = document.getElementById("searchBox").value

  findPinsByType(keyword).then((foundPins) => {
    const searchResultsList = document.getElementById("searchResults");

    while (searchResultsList.firstChild)
      searchResultsList.removeChild(searchResultsList.firstChild)

    Object.keys(foundPins).forEach((type) => {
      const pinListSection = document.createElement("li");
      pinListSection.appendChild(document.createTextNode(type));
      pinListSection.classList.add("typeListing")
      pinListSection.style.color = TYPES[type].color
      searchResultsList.appendChild(pinListSection);

      const pinListSectionList = document.createElement("ul");
      searchResultsList.appendChild(pinListSectionList)

      foundPins[type].forEach((pin) => {
        const pinListElement = document.createElement("li");
        const link = document.createElement("a");

        link.appendChild(document.createTextNode(pin["name"]));
        link.classList.add("pinListing")
        link.addEventListener("click", openPin)
        link.dataset.pinId = pin["id"]

        pinListElement.appendChild(link);
        pinListSectionList.appendChild(pinListElement);
      })
    })
  })
}