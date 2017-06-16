function increment(myInput) {
  myInput.value = (+myInput.value + 1) || 0;
}
function decrement(myInput) {
  myInput.value = (myInput.value - 1) || 0;
}
function incrementValue(element) {
  resetTempSetTimeout(); // Start the temp set timeout because we've done something
  element.text(Number(element.text()) + 1);
  if (element.text() > 100) element.text(100);
}
function decrementValue(element) {
  resetTempSetTimeout(); // Start the temp set timeout because we've done something
  element.text(Number(element.text()) - 1);
  if (element.text() < 40) element.text(40);
}

