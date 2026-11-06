/** Strict read-only resolution of a declared navigation composite for --check. */
import { stableString } from './deployer.mjs';

export const COMPOSITION_MARKER = 'x_observability_navigation';
const COMPOSER_URL = new URL('../../observability/homeassistant/navigation-composition.mjs', import.meta.url);
const EG4_VALIDATOR_URL = new URL('../../eg4_home_assistant/src/deployer.mjs', import.meta.url);

export async function loadCompositionDependencies(importer = value => import(value)) {
  try {
    const [composer, eg4] = await Promise.all([importer(COMPOSER_URL.href), importer(EG4_VALIDATOR_URL.href)]);
    if (composer.MARKER !== COMPOSITION_MARKER || typeof composer.composeNavigation !== 'function' ||
        !composer.ROUTES || typeof eg4.validateDashboard !== 'function') throw new Error('Unsupported trusted module contract');
    return { composeNavigation: composer.composeNavigation, routes: composer.ROUTES, validateEg4: eg4.validateDashboard };
  } catch {
    throw new Error('Declared Home Energy composition requires the trusted sibling observability navigation composer and EG4 validator; dependency unavailable or incompatible. No dashboard writes were attempted.');
  }
}

function assert(ok, message) { if (!ok) throw new Error(message); }
function expectedMetadata(metadata) {
  return { title: metadata.title, icon: metadata.icon, show_in_sidebar: metadata.showInSidebar, require_admin: metadata.requireAdmin };
}
function actualMetadata(metadata) {
  return Object.fromEntries(['title','icon','show_in_sidebar','require_admin'].map(k => [k, metadata[k] ?? (k === 'icon' ? null : false)]));
}

export async function resolveCheckDashboard({
  client, baseCandidate, existing, existingConfig, states, metadata,
  loadDependencies = loadCompositionDependencies,
}) {
  if (!existingConfig || !Object.hasOwn(existingConfig, COMPOSITION_MARKER)) {
    return { composed: false, candidate: baseCandidate, sourceCount: 0 };
  }
  const marker = existingConfig[COMPOSITION_MARKER];
  assert(marker && marker.schema === 1, 'Unsupported Home Energy composition marker; exact validation refused');
  assert(existing?.mode === 'storage' && existing.url_path === metadata.urlPath, 'Declared Home Energy composition has no exact storage dashboard');
  const { composeNavigation, routes, validateEg4 } = await loadDependencies();
  assert(routes.energy === metadata.urlPath, 'Trusted composition targets another Home Energy route');
  const dashboards = await client.call({ type: 'lovelace/dashboards/list' });
  const energyMatches = dashboards.filter(d => d.url_path === metadata.urlPath);
  assert(energyMatches.length === 1 && energyMatches[0].id === existing.id && energyMatches[0].mode === 'storage', 'Home Energy identity changed during composition check');
  assert(stableString(actualMetadata(energyMatches[0])) === stableString(expectedMetadata(metadata)), 'Home Energy metadata differs from its maintained contract');
  const input = { states, energy: { metadata: { ...energyMatches[0], ...expectedMetadata(metadata) }, config: baseCandidate } };
  let sourceCount = 0;
  for (const [role, route] of Object.entries(routes)) {
    if (role === 'energy') continue;
    const matches = dashboards.filter(d => d.url_path === route);
    assert(matches.length <= 1, 'Ambiguous composition source dashboard: ' + role);
    if (!matches.length && role === 'network') continue;
    assert(matches.length === 1 && matches[0].mode === 'storage', 'Required composition source dashboard is missing or not storage: ' + role);
    input[role] = { metadata: matches[0], config: await client.call({ type: 'lovelace/config', url_path: route, force: true }) };
    if (role === 'network') assert(matches[0].require_admin === true && input[role].config?.[COMPOSITION_MARKER]?.schema === 1, 'Existing Network route is not the trusted administrator composition');
    sourceCount++;
  }
  // The trusted generator receives the maintained seven-view candidate, never
  // a stripped live base or a marker-supplied module/path/allowlist.
  const plan = composeNavigation(input, { validateEg4 });
  const matches = plan.hubs?.filter(h => h.url_path === metadata.urlPath) ?? [];
  assert(matches.length === 1, 'Trusted composition did not produce exactly one Home Energy hub');
  assert(stableString(matches[0].metadata) === stableString(expectedMetadata(metadata)), 'Trusted composition changed the Home Energy metadata contract');
  assert(stableString(existingConfig) === stableString(matches[0].config), 'Declared Home Energy composite differs from its exact fresh recomputation; preserve edits and review/recompose');
  return { composed: true, candidate: matches[0].config, sourceCount };
}
