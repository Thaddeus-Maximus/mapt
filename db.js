// Should be sure to make things 'modular' so that we aren't dependent on firebase.
// Firebase is cheap, but it's Google. Don't leash to the hand that feeds you.

// Initialize Cloud Firestore through Firebase
const firebaseConfig = {
  apiKey: "AIzaSyD2fIyqYSUMCBnhJLKKpbgMWyIKjmpfBGE",
  authDomain: "mapt-ac61e.firebaseapp.com",
  projectId: "mapt-ac61e",
  storageBucket: "mapt-ac61e.appspot.com",
  messagingSenderId: "886960650416",
  appId: "1:886960650416:web:02729982a9ebc9f26de375"
};
firebase.initializeApp(firebaseConfig);
let db = firebase.firestore();

// Functions to work with the database

/* type
 * - name   (string)
 * - color  (string [#xxxxxx])
 * - fields (string [list,of,fields])
 */

/* pin
 * - type          (id)
 * - name          (string)
 * - searchdata    (string, lowercase of name)
 * - picture       (url)
 * - description   (string [json])
 * - parent (area) (id)
 * - coords        (list of tuples of x-y points... a point if one tuple, a polygon if more than one (lines are polygons right?))
 */

// This should be done once during setup, no more.
async function getTypes() {
  let dbQueryResult = await db.collection("types").get();
  return dbQueryResult.map((doc) => {return doc.data()});
}

async function sendType(data) {
  const defaultData = {
    "color": "#000000",
    "fields": []
  }

  normData = {... defaultData, ...data}

  let dbQueryResult = null;
  if ("id" in normData) {
    dbQueryResult = await db.collection("types").update(normData);
  } else {
    dbQueryResult = await db.collection("types").add(normData);
  }
  return dbQueryResult;
}

async function sendPin(data) {
  // ensure that the given pin exists
  // create if data.id undefined
  const defaultData = {
    "parent": null,
    "type": "pin",
    "name": "new_pin",
    "picture": "null.svg",
    "description": "",
    "coords": [[0,0]]
  }

  const normData = {... defaultData, ...data};

  let dbQueryResult = null;

  if ("id" in normData) {
    dbQueryResult = await db.collection("pins").update(normData);
  } else {
    dbQueryResult = await db.collection("pins").add(normData);
  }
  return dbQueryResult;
}

async function getPin(pinId) {
  // Find pin #pinId and then call f(data)
  let doc = await db.collection("pins").doc(pinId).get();
  let x = null;

  if (doc.exists) {
    let x = doc.data();
  }
  return x
}

async function getChildPins(pinId) {
  // Find pins whose immediate parent is pin #pinId and then call f(data)
  let dbQueryResult = await db.collection("pins").where("parent", "==", pinId).get();
  return dbQueryResult.map((doc) => {return doc.data()});
}

async function getRootPin() {
  // Find a pin whose immediate parent is null and call f(data)
  let dbQueryResult = await db.collection("pins").where("parent", "==", null).get();
  let x = null;
  dbQueryResult.forEach((doc) => {
    if (x === null)
      x = doc.data();
    else
      alert("There's more than one 'root' pin. I'm picking the first, but report this to the admin."); // TODO: Remove this
  })

  return x;
}

async function findPins(text) {
  // Find pins which match <text> and then call f(data)
  return null;
}