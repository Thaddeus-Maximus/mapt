// Should be sure to make things 'modular' so that we aren't dependent on firebase.
// Firebase is cheap, but it's Google. Don't leash to the hand that feeds you.

// Initialize Cloud Firestore through Firebase
var firebaseConfig = {
  apiKey: "AIzaSyD2fIyqYSUMCBnhJLKKpbgMWyIKjmpfBGE",
  authDomain: "mapt-ac61e.firebaseapp.com",
  projectId: "mapt-ac61e",
  storageBucket: "mapt-ac61e.appspot.com",
  messagingSenderId: "886960650416",
  appId: "1:886960650416:web:02729982a9ebc9f26de375"
};
firebase.initializeApp(firebaseConfig);
var db = firebase.firestore();

// Functions to work with the database

/* Schema reference
 *
 * types
 * - name   (string)
 * - color  (string [#xxxxxx])
 * - fields (string [list,of,fields])
 *
 * pins
 * - type          (id)
 * - name          (string)
 * - searchdata    (string, lowercase of name)
 * - picture       (url)
 * - description   (string [json])
 * - parent (area) (id)
 * - x (int)
 * - y (int)
 */

// This should be done once during setup, no more.
async function getTypes() {
  let result = await db.collection("types").get();
  let x = [];
  result.forEach((doc) => {
      x.push(doc.data());
    })
  return x;
}

async function sendType(data) {
  // ensure that the given type exists
  // create if data.id undefined
  let result = null;

  // required fields
  if (! "color" in data)
    data["color"] = "#000000";
  if (! "fields" in data)
    data["fields"] = "";

  if ("id" in data) {
    result = await db.collection("types").update(data);
  } else {
    result = await db.collection("types").add(data);
  }
  return result;
}

async function sendPin(data) {
  // ensure that the given pin exists
  // create if data.id undefined

  if (! "parent" in data)
    data["parent"] = null;
  if (! "type" in data)
    data["type"] = "pin";
  if (! "name" in data)
    data["name"] = "new_pin";
  if (! "picture" in data)
    data["picture"] = "null.svg";
  if (! "description" in data)
    data["description"] = "";
  if (! "x" in data)
    data["x"] = 0;
  if (! "y" in data)
    data["y"] = 0;

  let result = null;

  if ("id" in data) {
    result = await db.collection("pins").update(data);
  } else {
    result = await db.collection("pins").add(data);
  }
  return result;
}

async function getPin(id) {
  // Find pin #id and then call f(data)
  let doc = await db.collection("pins").doc(id).get();
  let x = null;

  if (doc.exists) {
    let x = doc.data();
  }
  return x
}

async function getChildPins(id) {
  // Find pins whose immediate parent is pin #id and then call f(data)
  let result = await db.collection("pins").where("parent", "==", id).get();
  let x = [];
  result.forEach((doc) => {
    x.push(doc.data());
  })

  return x;
}

async function getRootPin() {
  // Find a pin whose immediate parent is null and call f(data)
  let result = await db.collection("pins").where("parent", "==", null).get();
  let x = undefined;
  result.forEach((doc) => {
    if (x === undefined)
      x = doc.data();
    else
      alert("There's more than one 'root' pin. I'm picking the first, but report this to the admin.");
  })

  return x;
}

async function findPins(text) {
  // Find pins which match <text> and then call f(data)
  let result = await db.collection("pins").where("name", ">=", text).where("name", "<=", text+'\uf8ff').get();
  let x = []
  result.forEach((doc) => {
    let y = doc.data();
    y['id'] = doc.id;
    x.push(y);
  })

  return x;
}