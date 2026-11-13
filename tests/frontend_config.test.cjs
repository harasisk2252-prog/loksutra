// Regression: editing a story must preserve its language if /api/config is unavailable.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'app.js'), 'utf8');

for (const configured of [false, true]) {
  test('edit story with configuration ' + (configured ? 'loaded' : 'unavailable'), () => {
    const elements = new Map();
    function element(id) {
      if (!elements.has(id)) elements.set(id, {
        value: '', textContent: '', disabled: false, handlers: {},
        tagName: ['language', 'category'].includes(id) ? 'SELECT' : 'INPUT',
        options: [], classList: {toggle() {}, add() {}, remove() {}},
        addEventListener(event, handler) { this.handlers[event] = handler; },
        add(option) { this.options.push(option); },
        setAttribute() {}, scrollIntoView() {},
      });
      return elements.get(id);
    }
    const context = vm.createContext({
      document: {getElementById: element, querySelectorAll: () => []},
      Headers, AbortController, setTimeout, clearTimeout,
      window: {addEventListener() {}},
      fetch: () => new Promise(() => {}), confirm: () => true,
      matchMedia: () => ({matches: true}),
      Option: function(text, value) { this.text = text; this.value = value; },
    });
    vm.runInContext(source, context);
    vm.runInContext(
      "auth={authenticated:true}; config=" + (configured ? "{languages:{'pa-IN':'Punjabi'}}" : "null") +
      "; selected={id:'existing',title:'Existing story',person:'Contributor',region:'Punjab',language:'Punjabi',category:'Craft',transcript:'Original text',tags:'heritage'};",
      context
    );
    assert.doesNotThrow(() => element('editStory').handlers.click());
    assert.equal(element('title').value, 'Existing story');
    assert.equal(element('transcript').value, 'Original text');
    assert.equal(element('language').value, configured ? 'pa-IN' : 'Punjabi');
  });
}
