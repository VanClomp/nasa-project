<?php
/**
 * aboutus.php - Team & authors page for Planetary Analog Finder
 */
$teamMembers = [
    ['name' => 'Adam',    'initials' => 'AD', 'photo' => 'images/member_1.jpg'],
    ['name' => 'Antoni',  'initials' => 'AN', 'photo' => 'images/member_2.jpg'],
    ['name' => 'Franek',  'initials' => 'FR', 'photo' => 'images/member_3.jpg'],
    ['name' => 'Krzysiu', 'initials' => 'KR', 'photo' => 'images/member_4.jpg'],
    ['name' => 'Mikołaj', 'initials' => 'MI', 'photo' => 'images/member_5.jpg'],
];
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Planetary Analog Finder — About Us</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="style.css?v=<?php echo @filemtime(__DIR__ . '/style.css') ?: 1; ?>">
</head>
<body class="aboutus-page">

    <div class="ambient-backdrop"></div>

    <header class="navbar">
        <div class="nav-left">
            <a href="index.php" class="back-btn">Home</a>
            <span class="app-title">Planetary Analog Finder</span>
        </div>
        <div class="nav-telemetry">
            <span class="cpp-badge">NASA Space Apps 2026</span>
        </div>
    </header>

    <main class="aboutus-container">

        <section class="aboutus-hero">
            <span class="aboutus-eyebrow">OUR TEAM · AUTHORS</span>
            <h1 class="aboutus-title">About Us</h1>
            <p class="aboutus-lead">
                Our project has concluded with a creation of a website that finds a set of best earth analog locations for a chosen point on a surface of moon/mars based on 10+ indicators. For maximum flexibility, the user may change the lunar/martian time in which the mission will take place, and assign individually chosen values of importance for imitating every one of the indicators best. 
                <br><br> Our team did not want to focus much on existing analog locations, as those have been explored and researched deeply for years. The website we've created shows not only why the places that already have been operational have been chosen as the best to analog the conditions on moon and mars, and which indicator do they imitate best, but it also opens opportunities for new, un-researched locations to pop up backed by existing data. 
                <br><br> The project aims to find new analog places on earth, but with it come many more opportunities. Firstly, it summarizes data in one place, making it easier to check how well a given analog location used on earth will imitate conditions in different places on mars' surface. Also, besides the scientific role, it may be used in education, as it is approachable by a non-educated user to get to know martian and lunar conditions better.
            </p>
        </section>

        <!-- Group photo / banner slot -->
        <section class="aboutus-group-card">
            <div class="aboutus-group-photo">
                <img src="images/thats_we.jpg" alt="Our Team">
            </div>
            <div class="aboutus-group-caption">
                <div>
                    <h2>Who we are</h2>
                    <p>
                        We are first-year students of Computer Science, Mathematics, Physics, and Geology at the University of  (Poland).
                    </p>
                </div>
            </div>
        </section>

        <!-- Team members grid -->
        <section class="aboutus-section">
            <div class="aboutus-section-head">
                <span class="section-label" style="margin:0;">TEAM MEMBERS</span>
            </div>
            <div class="aboutus-grid">
                <?php foreach ($teamMembers as $member): ?>
                    <article class="aboutus-member-card">
                        <div class="aboutus-avatar">
                            <?php if (file_exists(__DIR__ . '/' . $member['photo'])): ?>
                                <img src="<?php echo htmlspecialchars($member['photo']); ?>" alt="<?php echo htmlspecialchars($member['name']); ?>">
                            <?php else: ?>
                                <span><?php echo htmlspecialchars($member['initials']); ?></span>
                            <?php endif; ?>
                        </div>
                        <div class="aboutus-member-info">
                            <h3><?php echo htmlspecialchars($member['name']); ?></h3>
                        </div>
                    </article>
                <?php endforeach; ?>
            </div>
        </section>

        <!-- Project highlights -->
        <section class="aboutus-highlights">
            <div class="aboutus-highlight-card">
                <span class="aboutus-hl-kicker">01 / DATA</span>
                <h4>Orbital &amp; Surface Datasets</h4>
                <p>Combines lunar and Martian datasets (LRO LOLA, Diviner, MOLA, TES, GRS) with Earth MODIS and cave catalogs.</p>
            </div>
            <div class="aboutus-highlight-card">
                <span class="aboutus-hl-kicker">02 / ENGINE</span>
                <h4>9D Weighted Similarity</h4>
                <p>Matches temperature, thermal inertia, roughness, moisture, dust, solar elevation, radiation, and terrain slope.</p>
            </div>
            <div class="aboutus-highlight-card">
                <span class="aboutus-hl-kicker">03 / VISUALIZATION</span>
                <h4>Interactive 3D Globes</h4>
                <p>Real-time Three.js globes with dual-planet comparison, landing-site presets, and temporal p(t) charts.</p>
            </div>
        </section>

    </main>

</body>
</html>
