import { useCallback, useEffect, useState } from 'react';

export function useResource(loader, dependencies = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    let active = true;
    setState((previous) => ({ ...previous, loading: true, error: null }));
    Promise.resolve().then(loader).then((data) => {
      if (active) setState({ data, loading: false, error: null });
    }).catch((error) => {
      if (active) setState((previous) => ({ ...previous, loading: false, error }));
    });
    return () => { active = false; };
    // The caller declares changing loader inputs in dependencies.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencies, attempt]);

  return { ...state, retry };
}
