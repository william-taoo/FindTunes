'use client';
import { useEffect, useState } from 'react';
import axios from 'axios';
import TopArtists from './components/TopArtists';
import TopTracks from './components/TopTracks';
import Playlists from './components/Playlists';
import Recommend, { type Recommendation } from './components/Recommend';
import useSongArtwork from './components/useSongArtwork';
export interface Track { track_id:string; track_name:string; track_url?:string; artist_names:string[]; artist_urls?:Record<string,string>; album_name:string; images?:string[]; }
export interface Artist { artist_id:string; artist_name:string; genres?:string[]; popularity:number; images?:string[]; artist_url?:string; }
export interface Playlist { playlist_id:string; playlist_name:string; playlist_image?:string[]; playlist_url?:string; }
export interface User { spotify_id:string; display_name:string; email:string; country:string; profile_image_url?:string; followers_count:number; product:string; spotify_profile_url?:string; }
export interface SpotifyUser { user:User; top_tracks:Track[]; top_artists:Artist[]; playlists:Playlist[]; }
const sections = [{id:'discover',label:'Discover',icon:'✦'}, {id:'rotation',label:'Your rotation',icon:'♫'}, {id:'artists',label:'Your artists',icon:'◎'}, {id:'playlists',label:'Your playlists',icon:'▤'}];
const DOMAIN = process.env.NEXT_PUBLIC_DOMAIN || 'http://localhost:8000';
export default function Dashboard() {
    const [data,setData] = useState<SpotifyUser|null>(null);
    const [loading,setLoading] = useState(true);
    useEffect(()=>{
        const fetchData = async()=>{
            try {
                const id=localStorage.getItem('spotify_id');
                if(!id) throw new Error('Spotify ID not found in localStorage');
                setData((await axios.get<SpotifyUser>(`${DOMAIN}/profile/${id}`,{withCredentials:true})).data);
            } catch(error) { console.error('Fetch error:',error); }
            finally { setLoading(false); }
        };
        void fetchData();
    },[]);
    useEffect(()=>{
        const syncUser=async()=>{
            const id=data?.user.spotify_id;
            if(!id || sessionStorage.getItem('alreadySynced')==='true') return;
            try { await axios.post(`${DOMAIN}/sync/${id}`,null,{withCredentials:true}); sessionStorage.setItem('alreadySynced','true'); }
            catch(error) { console.error('Error syncing user data:',error); }
        };
        if(!loading && data) void syncUser();
    },[loading,data]);
    if(loading) return <div className="ft-loading-screen"><span className="ft-spinner"/><p>Getting your music ready…</p></div>;
    if(!data?.user) return <div className="ft-loading-screen"><h1>Your music is one sign-in away.</h1><p>We couldn’t load your Spotify profile.</p><a className="ft-primary" href="/api/auth">Connect Spotify ↗</a></div>;
    return <DashboardView data={data}/>;
}
export function DashboardView({data,initialRecommendations}:{data:SpotifyUser;initialRecommendations?:Recommendation[]}) {
    const [activeSection, setActiveSection] = useState('discover');
    const scrollToSection = (id: string) => {
        document.getElementById(id)?.scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block:'start'});
    };
    useEffect(() => {
        let frame = 0;
        const update = () => {
            frame = 0;
            let active = 'discover';
            for (const section of sections) {
                if ((document.getElementById(section.id)?.getBoundingClientRect().top ?? Infinity) <= 140) active = section.id;
            }
            if (window.scrollY > 0 && window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) active = 'playlists';
            setActiveSection(active);
        };
        const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
        window.addEventListener('scroll', schedule, {passive:true});
        window.addEventListener('resize', schedule);
        const observer = new ResizeObserver(schedule);
        observer.observe(document.documentElement);
        update();
        return () => { window.removeEventListener('scroll', schedule); window.removeEventListener('resize', schedule); observer.disconnect(); cancelAnimationFrame(frame); };
    }, []);
    const [selectedTrack,setSelectedTrack]=useState<{id:string;name:string;artist:string}>();
    const [currentSong,setCurrentSong]=useState({name:'Bad Habit',artist:'Steve Lacy'});
    const knownTrack=data.top_tracks.find(track=>track.track_name.toLowerCase()===currentSong.name.toLowerCase() && track.artist_names.some(name=>name.toLowerCase()===currentSong.artist.toLowerCase()));
    const currentArtwork=useSongArtwork(currentSong.name,currentSong.artist,knownTrack?.track_id,knownTrack?.images?.[0]);
    const artworkById=Object.fromEntries(data.top_tracks.filter(track=>track.images?.[0]).map(track=>[track.track_id,track.images![0]]));
    return <div className="ft-app-shell">
        <aside className="ft-sidebar">
            <button type="button" className="ft-brand" onClick={()=>scrollToSection("discover")}><span className="ft-brand-icon">♫</span>FindTunes<span className="ft-brand-dot">.</span></button>
            <p className="ft-sidebar-caption">MAKE ROOM FOR NEW MUSIC</p>
            <nav aria-label="Dashboard navigation">{sections.map(section => <button type="button" key={section.id} className={activeSection === section.id ? 'ft-nav-primary' : undefined} aria-current={activeSection === section.id ? 'location' : undefined} onClick={()=>scrollToSection(section.id)}><span aria-hidden="true">{section.icon}</span>{section.label}</button>)}</nav>
            <div className="ft-sidebar-profile"><img src={data.user.profile_image_url || '/no-picture.png'} alt=""/><div><strong>{data.user.display_name}</strong><span>Spotify connected <i/></span></div></div>
        </aside>
        <main className="ft-main">
            <header className="ft-topbar"><span>Discover / <strong>For you</strong></span><a href={data.user.spotify_profile_url} target="_blank" rel="noopener noreferrer" className="ft-account-link">Your Spotify ↗</a></header>
            <section className="ft-hero" aria-labelledby="discovery-title">
                <div><h1 id="discovery-title">Same feeling.<br/><span>New favorite.</span></h1><p className="ft-hero-copy">Find songs that speak your language.<br/>Discover the connections hiding in the lyrics.</p></div>
                <div className="ft-hero-art"><div className="ft-orbit" aria-hidden="true"/><div className="ft-hero-disc ft-song-disc" aria-hidden="true">{currentArtwork ? <img src={currentArtwork} alt=""/> : <span>♪</span>}</div><span className="ft-art-caption">{currentSong.name || 'Choose a song'}{currentSong.artist && <><br/>{currentSong.artist}</>}</span></div>
            </section>
            <Recommend selectedTrack={selectedTrack} artworkById={artworkById} initialRecommendations={initialRecommendations} onSongChange={setCurrentSong}/>
            <div className="ft-library-section" id="rotation"><TopTracks top_tracks={data.top_tracks} onSelect={track=>{setSelectedTrack({id:track.track_id,name:track.track_name,artist:track.artist_names[0] || ''});scrollToSection('discover');}}/></div>
            <div className="ft-library-section" id="artists"><TopArtists top_artists={data.top_artists}/></div>
            <div className="ft-library-section" id="playlists"><Playlists playlists={data.playlists}/></div>
            <footer className="ft-footer"><span>FindTunes<span className="ft-brand-dot">.</span></span><span>Made for the music you haven’t found yet.</span></footer>
        </main>
    </div>;
}
