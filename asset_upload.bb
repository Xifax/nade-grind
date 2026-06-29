#!/usr/bin/env bb

(require '[babashka.fs           :as fs]
         '[babashka.process      :as proc]
         '[babashka.http-client  :as http]
         '[cheshire.core         :as json]
         '[clojure.string        :as str])

;;; ---------------------------------------------------------------------------
;;; Config
;;; ---------------------------------------------------------------------------

(def version         "0.2.0")
(def project         "xifax/nade_grind")
(def project-encoded "xifax%2Fnade_grind")
(def release-name    (str "v" version "-nigiri"))
(def notes           "Linux BIN & Windows EXE")

(def files
  {"nade.bin" "dist/nade.bin"
   "nade.exe" "dist/nade.exe"})

;;; ---------------------------------------------------------------------------
;;; .env loader  (bash `set -a; source .env; set +a` equivalent)
;;; ---------------------------------------------------------------------------

(defn parse-env-file [path]
  (when (fs/exists? path)
    (->> (str/split-lines (slurp path))
         (keep (fn [line]
                 (let [t (str/trim line)]
                   (when (and (not (str/blank? t))
                              (not (str/starts-with? t "#"))
                              (str/includes? t "="))
                     (let [idx (str/index-of t "=")]
                       [(subs t 0 idx) (subs t (inc idx))])))))
         (into {}))))

(def file-env (parse-env-file ".env"))

(when-not (seq file-env)
  (println "Warning: .env file not found. PRIVATE_TOKEN must be set manually."))

(defn getenv
  "Check .env-file values first, fall back to the real environment."
  [k]
  (or (get file-env k) (System/getenv k)))

;;; ---------------------------------------------------------------------------
;;; Guards
;;; ---------------------------------------------------------------------------

(def private-token
  (or (getenv "PRIVATE_TOKEN")
      (do (binding [*out* *err*]
            (println "Error: PRIVATE_TOKEN environment variable is not set"))
          (System/exit 1))))

(doseq [[_ local-file] files]
  (when-not (fs/exists? local-file)
    (binding [*out* *err*]
      (println (str "Error: File not found: " local-file)))
    (System/exit 1)))

;;; ---------------------------------------------------------------------------
;;; Helpers
;;; ---------------------------------------------------------------------------

(defn pkg-url [filename]
  (str "https://gitlab.com/api/v4/projects/" project-encoded
       "/packages/generic/nade_grind/" version "/" filename))

(defn assert-ok! [resp context]
  (when (>= (:status resp) 400)
    (binding [*out* *err*]
      (println (str "Error: " context " → HTTP " (:status resp)))
      (println (:body resp)))
    (System/exit 1)))

;;; ---------------------------------------------------------------------------
;;; 1. Upload binaries to the Package Registry
;;; ---------------------------------------------------------------------------

(println "=== Uploading packages to GitLab Package Registry ===")

(doseq [[asset-name local-file] files]
  (println (str "Uploading " local-file " ..."))
  (let [resp (http/put (pkg-url asset-name)
                       {:headers {"PRIVATE-TOKEN" private-token}
                        :body    (fs/file local-file)})]
    (assert-ok! resp (str "upload " local-file))))

;;; ---------------------------------------------------------------------------
;;; 2. Create / update the release  (|| true → :continue true)
;;; ---------------------------------------------------------------------------

(println "\n=== Creating/updating release ===")

(proc/shell {:continue true}
            "glab" "release" "create" (str "v" version)
            "--name"  release-name
            "--notes" notes)

;;; ---------------------------------------------------------------------------
;;; 3. Sync asset links
;;; ---------------------------------------------------------------------------

(println "\n=== Syncing release asset links ===")

(doseq [[asset-name _] files]
  (let [links-json (-> (proc/shell {:out :string}
                                   "glab" "api"
                                   (str "projects/" project-encoded
                                        "/releases/v" version "/assets/links"))
                       :out
                       (json/parse-string true))  ; true → keyword keys
        existing-id (->> links-json
                         (some #(when (= (:name %) asset-name) (:id %))))]

    (when existing-id
      (println (str "Removing old link for " asset-name " (ID: " existing-id ")"))
      (proc/shell "glab" "api" "-X" "DELETE"
                  (str "projects/" project-encoded
                       "/releases/v" version "/assets/links/" existing-id)))

    (println (str "Creating asset link for " asset-name))
    (proc/shell "glab" "api" "-X" "POST"
                (str "projects/" project-encoded
                     "/releases/v" version "/assets/links")
                "--field" (str "name=" asset-name)
                "--field" (str "url=" (pkg-url asset-name)))))

(println (str "\n✅ Done. Release v" version " is ready."))
