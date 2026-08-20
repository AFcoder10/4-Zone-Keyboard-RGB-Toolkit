import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import iconImg from '../assets/rgb_wheel.ico';
import previewImg from '../assets/preview.png';

function Home() {
  const [latestRelease, setLatestRelease] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState('https://github.com/AFcoder10/4-Zone-Keyboard-RGB-Toolkit/releases/latest');
  const [versionText, setVersionText] = useState('Download');

  useEffect(() => {
    // Add scroll animation observer
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
        }
      });
    }, { threshold: 0.1 });

    const animatedElements = document.querySelectorAll('.anim-scroll');
    animatedElements.forEach(el => observer.observe(el));

    const controller = new AbortController();

    // Fetch releases
    fetch('https://api.github.com/repos/AFcoder10/4-Zone-Keyboard-RGB-Toolkit/releases', { signal: controller.signal })
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data) && data.length > 0) {
          const latest = data[0];
          setLatestRelease(latest);
          
          // Find the exe asset
          const exeAsset = latest.assets?.find(asset => asset.name.endsWith('.exe'));
          if (exeAsset) {
            setDownloadUrl(exeAsset.browser_download_url);
            setVersionText(`Download ${latest.tag_name}`);
          }
        }
      })
      .catch(err => {
        if (err.name === 'AbortError') return;
        console.error("Failed to fetch releases:", err);
      });

    return () => {
      animatedElements.forEach(el => observer.unobserve(el));
      controller.abort();
    };
  }, []);

  return (
    <>
      <nav>
        <div className="nav-inner">
          <Link to="/" className="nav-logo">
            <img src={iconImg} alt="4ZoneRGB" width="24" height="24" />
            <span>4 Zone RGB Toolkit</span>
          </Link>
          <div className="nav-links">
            <a href="#" onClick={(e) => { e.preventDefault(); document.getElementById('features').scrollIntoView({ behavior: 'smooth' }); }}>Features</a>
            <Link to="/changelog">Changelog</Link>
            <a href="https://rgb-toolkit-telemetry.vercel.app" target="_blank" rel="noreferrer">Telemetry</a>
            <a href="https://discord.gg/ecKwmsDBXg" target="_blank" rel="noreferrer">Discord</a>
            <a href={downloadUrl} className="nav-cta">{versionText}</a>
          </div>
        </div>
      </nav>

      <header className="hero">
        <div className="hero-inner">
          <p className="eyebrow anim" style={{ '--d': 0 }}>Open-source · Free forever</p>
          <h1 className="anim" style={{ '--d': 1 }}>Unlock Your Laptop's<br /><span className="grad">True Colors</span></h1>
          <p className="subtitle anim" style={{ '--d': 2 }}>Hardware &amp; software RGB control designed for Lenovo LOQ and Legion laptops.</p>
          <div className="hero-btns anim" style={{ '--d': 3 }}>
            <a href={downloadUrl} className="btn-fill">{versionText}</a>
            <Link to="/changelog" className="btn-outline">View Changelog</Link>
            <a href="https://discord.gg/ecKwmsDBXg" target="_blank" rel="noreferrer" className="btn-outline" style={{marginLeft: '10px'}}>Join Discord</a>
          </div>
        </div>
      </header>

      <section className="showcase anim-scroll">
        <img src={previewImg} alt="App preview" />
      </section>

      <section id="features" className="features">
        <h2 className="anim-scroll">Features</h2>
        <p className="features-lead anim-scroll">All the controls you need — nothing you don't.</p>

        <div className="glossary-grid">
          <div className="glossary-col anim-scroll">
            <h3>Hardware Modes</h3>
            <p className="col-desc">Zero CPU usage. Processed directly by the keyboard controller.</p>
            <ul className="feature-list">
              <li><strong>Off</strong> — Complete darkness for distraction-free work.</li>
              <li><strong>Static</strong> — Solid, uninterrupted color across all zones.</li>
              <li><strong>Breath</strong> — Gentle pulsing effect of a single color.</li>
              <li><strong>Smooth</strong> — Seamless transitions between primary colors.</li>
              <li><strong>Wave</strong> — Classic RGB wave effect traversing the keyboard.</li>
            </ul>

            <h3 className="mt-xl">App Utilities</h3>
            <p className="col-desc">Built-in settings for a seamless, automated experience.</p>
            <ul className="feature-list">
              <li><strong>Auto-Launch</strong> — Starts silently with Windows.</li>
              <li><strong>Auto-Off Battery</strong> — Disables RGB when unplugged to save power.</li>
              <li><strong>Live Telemetry</strong> — View real-time statistics of active users currently using the app globally.</li>
              <li><strong>System Tray</strong> — Runs quietly in the background.</li>
              <li><strong>Hotkeys</strong> — Quickly cycle modes, toggle effects, or adjust brightness using keyboard shortcuts.</li>
            </ul>
          </div>

          <div className="glossary-col anim-scroll">
            <h3>Software Modes</h3>
            <p className="col-desc">Highly reactive lighting powered by optimized software algorithms.</p>
            <ul className="feature-list">
              <li><strong>Ambient Screen</strong> — Synchronizes your keyboard colors with whatever is displayed on your monitor.</li>
              <li><strong>Audio Visualizer</strong> — Real-time reactive lighting based on your system's audio output.</li>
              <li><strong>Battery Visualizer</strong> — Turns your keyboard into a live battery gauge.</li>
              <li><strong>Pomodoro Timer</strong> — Productivity lighting that tracks your work and break intervals visually.</li>
              <li><strong>Mouse-Reactive</strong> — Lights up the keyboard zones corresponding to your cursor position.</li>
              <li><strong>Temperature</strong> — Changes color based on your system's CPU/GPU temperatures.</li>
              <li><strong>Smooth Wave</strong> — A highly customizable, fluid color wave that travels across zones.</li>
              <li><strong>Lightning</strong> — Random, high-intensity flashes mimicking a thunderstorm.</li>
              <li><strong>Party</strong> — Fast-paced, random, and energetic color cycling.</li>
              <li><strong>Realistic Fire</strong> — Warm, flickering gradient animations simulating burning flames.</li>
              <li><strong>Scanner</strong> — A sweeping light effect similar to classic sci-fi visors.</li>
              <li><strong>Aurora Borealis</strong> — Slow, majestic color blending inspired by the northern lights.</li>
              <li><strong>Meteor Shower</strong> — Streaks of light falling rapidly across the keyboard.</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="star-section anim-scroll">
        <p>If you like this project, consider giving it a</p>
        <a href="https://github.com/AFcoder10/4-Zone-Keyboard-RGB-Toolkit" target="_blank" rel="noreferrer" className="star-link">⭐ Star on GitHub</a>
      </section>

      <footer>
        <span>© 2026 AFcoder10 · GPL-3.0 License</span>
      </footer>
    </>
  );
}

export default Home;
