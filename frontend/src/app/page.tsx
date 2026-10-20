"use client";

import { useState, type CSSProperties } from 'react';

// Curated from the saved Spotify favorites; public artist imagery only.
const portraits = [
  {name:'Lil Uzi Vert', image:'0eb7019b6bb9ce078a9ac03b'},
  {name:'Playboi Carti', image:'ba50ca67ffc3097f6ea1710a'},
  {name:'Travis Scott', image:'19c2790744c792d05570bb71'},
  {name:'Drake', image:'4293385d324db8558179afd9'},
  {name:'Tyler, The Creator', image:'df2728294ff77dd11eeb18fb'},
  {name:'Frank Ocean', image:'ee3123e593174208f9754fab'},
  {name:'SZA', image:'fd0a9fb6c252a3ba44079acf'},
  {name:'Daniel Caesar', image:'e4d94f7cbebb17504c25d419'},
  {name:'KETTAMA', image:'65eb52c5da399f337626be07'},
  {name:'John Summit', image:'20662b32f3dbabad755dfb53'},
  {name:"it's murph", image:'44f42433d8924aa0c9ff0878'},
  {name:'Dom Dolla', image:'9290e172cbcacc0521b02b11'},
];
const demos = [
  {title:'Pink + White', artist:'Frank Ocean', theme:'Memory, love, and the things that stay.', cover:'https://i.scdn.co/image/ab67616d0000b273c5649add07ed3720be9d5526'},
  {title:'Snooze', artist:'SZA', theme:'Vulnerability with someone on your mind.', cover:'https://i.scdn.co/image/ab67616d0000b273bc18bdade69ec5ef0bb25b17'},
  {title:'Dark Red', artist:'Steve Lacy', theme:'The uncertainty of wanting someone close.', cover:'https://i.scdn.co/image/ab67616d0000b2733d2dfa42f771cd458b194979'},
];
export default function Home() {
  const [paused, setPaused] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  return <main className={`ft-landing ${paused ? 'ft-motion-paused' : ''}`}>
    <nav className="ft-landing-nav" aria-label="Main navigation">
      <a href="/" className="ft-landing-brand"><span>♫</span> FindTunes<b>.</b></a>
      <a className="ft-landing-about" href="#how-it-works">How it works</a>
      <a className="ft-landing-login" href="/api/auth">Connect Spotify <span>↗</span></a>
    </nav>
    <section className="ft-landing-hero" aria-labelledby="landing-title">
      <div className="ft-landing-copy">
        <p className="ft-landing-eyebrow"><span/> FOR YOUR NEXT MUSICAL OBSESSION</p>
        <h1 id="landing-title">Same feeling.<br/><em>New favorite.</em></h1>
        <p className="ft-landing-description">You know the feeling.<br/>Find the song that gives it back.</p>
        <p className="ft-landing-subcopy">Discover songs connected by lyrics. Explore the words, stories, and sounds that bring them together.</p>
        <a className="ft-landing-cta" href="/api/auth"><span aria-hidden="true">♫</span> Find my next favorite <span aria-hidden="true">↗</span></a>
        <p className="ft-landing-footnote">Connect your Spotify. Follow your curiosity.</p>
      </div>
      <div className="ft-portrait-stage">
        <div className="ft-stage-grid" aria-hidden="true"/>
        <div className="ft-portrait-flow" aria-hidden="true">{[0,1,2].map(lane=><div className={`ft-portrait-lane ft-lane-${lane}`} key={lane}>
          {[0,1].map(copy=><div className="ft-portrait-sequence" key={copy}>{[0,1,2,3].map((item)=> <div className="ft-portrait-circle" key={item} title={portraits[lane*4+item].name} style={{'--portrait-tone': `${(lane*70+item*30)%360}deg`} as CSSProperties}>
            <img src={`https://i.scdn.co/image/ab67616100005174${portraits[lane*4+item].image}`} alt="" onError={event=>{event.currentTarget.src='/no-picture.png'; event.currentTarget.onerror=null;}}/>
          </div>)}</div>)}
        </div>)}</div>
        <div className="ft-floating-note"><span className="ft-note-icon">✦</span><div><small>LESS ENDLESS SCROLLING</small><strong>More “where has this been?”</strong></div></div>
        <button className="ft-motion-toggle" type="button" aria-pressed={paused} onClick={()=>setPaused(!paused)}>{paused ? '▶ Resume motion' : 'Ⅱ Pause motion'}</button>
      </div>
    </section>
    <section className="ft-landing-demo" aria-labelledby="demo-title">
      <div className="ft-demo-heading"><div><p className="ft-landing-eyebrow">A LITTLE FAMILIAR. A LITTLE UNEXPECTED.</p><h2 id="demo-title">One song opens a whole new world.</h2></div><span className="ft-demo-label">Illustrative demo · tap a card</span></div>
      <div className="ft-demo-seed"><img className="ft-demo-seed-cover" src="https://i.scdn.co/image/ab67616d0000b2736938311000a0e494a26986e5" alt="Bad Habit cover art" width={54} height={54}/><div><small>START WITH</small><strong>Bad Habit <span>— Steve Lacy</span></strong></div><span className="ft-seed-trail" aria-hidden="true">······························································· ✦</span><span className="ft-seed-hint">Follow the feeling</span></div>
      <div className="ft-demo-cards">{demos.map((song,index)=><button type="button" key={song.title} className={`ft-demo-card ${selected===index ? 'ft-demo-selected' : ''}`} aria-expanded={selected===index} onClick={()=>setSelected(selected===index ? null : index)}>
        <div className="ft-demo-art"><img src={song.cover} alt={`${song.title} cover art`} loading="lazy"/><span className="ft-demo-card-arrow" aria-hidden="true">↗</span></div>
        <div className="ft-demo-card-info"><h3>{song.title}</h3><p>{song.artist}</p>{selected===index && <div className="ft-demo-explanation"><strong>An example connection</strong><p>{song.theme}</p><small>Sample copy, not a live recommendation or verified lyric analysis. Connect Spotify to explore real matches.</small></div>}</div>
      </button>)}</div>
    </section>
    <section className="ft-landing-steps" id="how-it-works" aria-labelledby="steps-title"><div><p className="ft-landing-eyebrow">LET YOUR TASTE TAKE THE LEAD</p><h2 id="steps-title">A new rabbit hole.<br/>In three little steps.</h2></div><ol>
      <li><span>01</span><div><h3>Bring a song you love.</h3><p>Start with a favorite, or pick something from your Spotify rotation.</p></div></li>
      <li><span>02</span><div><h3>Find a lyrical connection.</h3><p>Discover songs with related words and themes, beyond the usual artist connections.</p></div></li>
      <li><span>03</span><div><h3>Get closer to the music.</h3><p>Explore lyric explanations and available reviews or production context.</p></div></li>
    </ol></section>
    <footer className="ft-landing-footer"><a href="/" className="ft-landing-brand">FindTunes<b>.</b></a><span>For the music you haven’t found yet.</span><a href="/api/auth">Let’s find it ↗</a></footer>
  </main>;
}
