// Exercise the actual component without adding a browser or test-runner dependency.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const filename = path.resolve(__dirname, '../src/app/dashboard/components/ResearchDetails.tsx');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const component = new Module(filename, module);
component.filename = filename;
component.paths = module.paths;
component._compile(compiled, filename);
const { default: Details, musicalOutcome, vibeDescription } = component.exports;
const source = { id: 's1', url: 'https://example.com/review', title: 'Song review',
    text: 'A mellow, dreamy atmosphere with airy vocals.', kind: 'written_excerpt' };
const seed = { song: {title:'Input Song',artist:'Input Artist',version:'original'},
    vibe:'Mellow and atmospheric.', sources:[source] };
function result(outcome, overrides = {}) {
    return {status: ['searching','analyzing'].includes(outcome) ? 'running' : 'complete',
        profile:{mode:'vibe',song:{title:'Target Song',artist:'Target Artist',version:'original'},
            vibe:outcome === 'vibe_ready' ? 'Dreamy and relaxed, with a brighter feel than your input song.' : null,
            compares_to_seed:true, sources:['searching','no_sources','search_failed'].includes(outcome) ? [] : [source],
            profile:{},findings:[],errors:[],cached:false,outcome,...overrides}};
}
const render = value => renderToStaticMarkup(React.createElement(Details,{result:value,seed}));
const ready = result('vibe_ready');
const markup = render(ready);
assert(markup.includes(ready.profile.vibe));
assert(markup.includes(seed.vibe));
assert(markup.includes('Input Song'));
assert(markup.indexOf(ready.profile.vibe) < markup.indexOf('Sources behind the vibe'));
assert(!markup.includes('passed the evidence check'));
assert(!markup.includes('prominence rating'));
assert(!markup.includes('AI musical observation'));
assert.equal(vibeDescription(ready),ready.profile.vibe);
assert.equal(vibeDescription({...ready,vibe_description:'Card-ready comparison.'}),'Card-ready comparison.');
for (const [outcome,label] of [
    ['searching','Finding the vibe'],['analyzing','Writing the vibe description'],
    ['sources_only','Sources only'],['no_sources','Vibe description unavailable'],
    ['analysis_failed','Vibe description unavailable'],['search_failed','Vibe lookup unavailable'],
]) {
    const value=result(outcome);
    const html=render(value);
    assert(html.includes(label),outcome);
    assert.equal(musicalOutcome(value).code,outcome);
    if(value.profile.sources.length) assert(html.includes(source.text),outcome);
    assert(!html.includes('No reliable AI profile'),outcome);
}
assert.equal(vibeDescription(result('analyzing')),null);
assert.equal(musicalOutcome(undefined).code,'unavailable');
assert.equal(renderToStaticMarkup(React.createElement(Details, {
    result: {status:'evidence_only', profile:null, sources:{seed:'https://genius.com/123', candidate:'https://genius.com/456'}},
})), '');
console.log('Vibe UI checks passed: card description, input-song context, source links, loading/failure states, and no ratings/checklist.');
