"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, fetchAcademicCatalog } from "../../lib/api";
import { useAuth } from "../../lib/providers/AuthProvider";

function RegisterPage() {
  const router = useRouter();
  const { register, user, isLoading } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [academicCatalog, setAcademicCatalog] = useState([]);
  const [facultyId, setFacultyId] = useState("");
  const [careerId, setCareerId] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [isLoadingCatalog, setIsLoadingCatalog] = useState(false);

  useEffect(() => {
    if (!isLoading && user) {
      router.replace("/dashboard");
    }
  }, [isLoading, router, user]);

  useEffect(() => {
    let cancelled = false;

    const loadCatalog = async () => {
      setIsLoadingCatalog(true);
      try {
        const rows = await fetchAcademicCatalog();
        if (cancelled) {
          return;
        }
        const catalog = rows || [];
        setAcademicCatalog(catalog);
        const firstFaculty = catalog[0];
        setFacultyId(firstFaculty?.id || "");
        setCareerId(firstFaculty?.careers?.[0]?.id || "");
      } catch (requestError) {
        if (!cancelled) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "No se pudo cargar el catalogo academico."
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoadingCatalog(false);
        }
      }
    };

    void loadCatalog();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedFaculty = academicCatalog.find((faculty) => faculty.id === facultyId);
  const availableCareers = selectedFaculty?.careers || [];

  const handleFacultyChange = (event) => {
    const nextFacultyId = event.target.value;
    const nextFaculty = academicCatalog.find((faculty) => faculty.id === nextFacultyId);
    setFacultyId(nextFacultyId);
    setCareerId(nextFaculty?.careers?.[0]?.id || "");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Las contrasenas no coinciden.");
      return;
    }

    if (!facultyId || !careerId) {
      setError("Selecciona tu facultad y carrera.");
      return;
    }

    setSubmitting(true);

    try {
      const payload = await register(email, password, { facultyId, careerId });
      if (payload?.access_token) {
        router.push("/dashboard");
      }
    } catch (requestError) {
      if (requestError instanceof ApiError) {
        setError(requestError.message);
      } else if (requestError instanceof Error) {
        setError(requestError.message);
      } else {
        setError("No se pudo completar el registro.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <p className="auth-eyebrow">Asesor IA de tesis</p>
        <h1>Crear cuenta</h1>
        <p className="auth-description">
          Registra tu cuenta para procesar tesis y conversar con el revisor inteligente.
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            Correo
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="estudiante@universidad.edu"
              required
              autoComplete="email"
            />
          </label>

          <label>
            Contrasena
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Minimo 6 caracteres"
              required
              minLength={6}
              autoComplete="new-password"
            />
          </label>

          <label>
            Confirmar contrasena
            <input
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="Repite la contrasena"
              required
              minLength={6}
              autoComplete="new-password"
            />
          </label>

          <label>
            Facultad
            <select
              className="field-select"
              value={facultyId}
              onChange={handleFacultyChange}
              required
              disabled={isLoadingCatalog || submitting}
            >
              {academicCatalog.map((faculty) => (
                <option key={faculty.id} value={faculty.id}>
                  {faculty.acronym} - {faculty.name}
                </option>
              ))}
            </select>
          </label>

          <label>
            Carrera
            <select
              className="field-select"
              value={careerId}
              onChange={(event) => setCareerId(event.target.value)}
              required
              disabled={isLoadingCatalog || submitting || !availableCareers.length}
            >
              {availableCareers.map((career) => (
                <option key={career.id} value={career.id}>
                  {career.name}
                </option>
              ))}
            </select>
          </label>

          <button
            className="button button-primary"
            type="submit"
            disabled={submitting || isLoadingCatalog || !facultyId || !careerId}
          >
            {submitting ? "Creando cuenta..." : "Crear cuenta"}
          </button>
        </form>

        {error ? <p className="inline-error">{error}</p> : null}

        <p className="auth-switch">
          Ya tienes cuenta? <Link href="/login">Iniciar sesion</Link>
        </p>
      </section>
    </main>
  );
}

export default RegisterPage;
