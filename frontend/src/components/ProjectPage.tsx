import { FC } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { useDeleteProject } from '../core/api';
//import { useUserProjects } from '../core/api';
import { useAppContext } from '../core/context';
import { AnnotationDisagreementManagement } from './AnnotationDisagreementManagement';
import { ProjectStatistics } from './ProjectStatistics';
import { SchemesManagement } from './SchemesManagement';
import { ProjectPageLayout } from './layout/ProjectPageLayout';
/**
 * Component to display the project page
 */

export const ProjectPage: FC = () => {
  const { projectName } = useParams();

  const {
    appContext: { currentScheme, currentProject: project, history },
    setAppContext,
  } = useAppContext();

  const navigate = useNavigate();

  // function to delete project
  const deleteProject = useDeleteProject();
  const actionDelete = () => {
    if (projectName) {
      deleteProject(projectName);
      navigate(`/projects/`);
    }
  };

  // function to clear history
  const actionClearHistory = () => {
    setAppContext((prev) => ({ ...prev, history: [] }));
  };

  const activeUsers = project?.users?.active ? project?.users?.active : [];

  return (
    projectName && (
      <ProjectPageLayout projectName={projectName}>
        {project && (
          <div className="container-fluid">
            <div className="row">
              <h2 className="subsection">Project panel</h2>
            </div>
            <div className="text-muted smalfont-weight-light">
              Recent users{' '}
              {activeUsers.map((e) => (
                <span className="badge rounded-pill text-bg-light text-muted me-2" key={e}>
                  {e}
                </span>
              ))}
            </div>

            <div className="row">
              <SchemesManagement projectSlug={projectName} />
            </div>

            {currentScheme && (
              <div className="row">
                <ProjectStatistics projectSlug={projectName} scheme={currentScheme} />
              </div>
            )}

            <div className="row mt-4">
              <div className="col-12">
                <details className="custom-details">
                  <summary className="custom-summary">Disagreement management</summary>
                  <span className="explanations">In development</span>
                  {currentScheme && <AnnotationDisagreementManagement projectSlug={projectName} />}
                </details>

                <details className="custom-details">
                  <summary className="custom-summary">Session</summary>
                  <span className="explanations">Element annotated during this session</span>
                  <div>{JSON.stringify(history, null, 2)}</div>
                  <button onClick={actionClearHistory} className="delete-button">
                    Clear history
                  </button>
                </details>

                <details className="custom-details">
                  <summary className="custom-summary">Parameters</summary>
                  <span className="explanations">Parameters of this project</span>
                  <div>{JSON.stringify(project.params, null, 2)}</div>
                  <button onClick={actionDelete} className="delete-button">
                    Delete project
                  </button>
                </details>
              </div>
            </div>
          </div>
        )}
      </ProjectPageLayout>
    )
  );
};
