import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Link } from 'react-router-dom';
import iconImg from '../assets/rgb_wheel.ico';

function Changelog() {
  const [allReleases, setAllReleases] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    window.scrollTo(0, 0);
    // Fetch releases
    fetch('https://api.github.com/repos/AFcoder10/4-Zone-Keyboard-RGB-Toolkit/releases')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data) && data.length > 0) {
          setAllReleases(data);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch releases:", err);
        setLoading(false);
      });
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
            <Link to="/">Back to Home</Link>
          </div>
        </div>
      </nav>

      <section className="changelog-section" style={{ paddingTop: '120px', minHeight: '80vh' }}>
        <h2>Version History</h2>
        <p className="col-desc" style={{textAlign: 'center'}}>A complete history of updates and release notes.</p>
        
        {loading ? (
          <p style={{ textAlign: 'center', marginTop: '2rem' }}>Loading release notes...</p>
        ) : (
          <div className="changelog-list">
            {allReleases.map(release => (
              <div key={release.id} className="release-card">
                <div className="release-header">
                  <h3>{release.name || release.tag_name}</h3>
                  <span className="release-date">
                    {new Date(release.published_at).toLocaleDateString(undefined, {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })}
                  </span>
                </div>
                <div className="release-body">
                  <ReactMarkdown>{release.body}</ReactMarkdown>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <footer>
        <span>© 2026 AFcoder10 · GPL-3.0 License</span>
      </footer>
    </>
  );
}

export default Changelog;
