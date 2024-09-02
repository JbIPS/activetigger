import { ChangeEvent, FC, useCallback, useEffect, useMemo, useState } from 'react';
import { IoMdReturnLeft } from 'react-icons/io';
import { Link, useNavigate, useParams } from 'react-router-dom';

import {
  useAddAnnotation,
  useGetElementById,
  useGetNextElementId,
  useStatistics,
  useUpdateSimpleModel,
} from '../core/api';
import { useAuth } from '../core/auth';
import { useAppContext } from '../core/context';
import { ElementOutModel } from '../types';
import { LabelsManagement } from './LabelsManagement';
import { ProjectionManagement } from './ProjectionManagement';
import { SelectCurrentScheme } from './SchemesManagement';
import { SimpleModelManagement } from './SimpleModelManagement';
import { ProjectPageLayout } from './layout/ProjectPageLayout';

import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';

export const ProjectAnnotationPage: FC = () => {
  const { projectName, elementId } = useParams();
  const { authenticatedUser } = useAuth();
  const {
    appContext: {
      currentScheme,
      reFetchCurrentProject,
      currentProject: project,
      selectionConfig,
      freqRefreshSimpleModel,
      history,
    },
    setAppContext,
  } = useAppContext();

  const navigate = useNavigate();
  const [element, setElement] = useState<ElementOutModel | null>(null); //state for the current element

  // hooks to manage element
  const { getNextElementId } = useGetNextElementId(
    projectName || null,
    currentScheme || null,
    history,
  );
  const { getElementById } = useGetElementById(projectName || null, currentScheme || null);

  // hooks to manage annotation
  const { addAnnotation } = useAddAnnotation(projectName || null, currentScheme || null);

  // define parameters for configuration panels
  const availableFeatures = project?.features.available ? project?.features.available : [];
  const availableSimpleModels = project?.simplemodel.options ? project?.simplemodel.options : {};
  const currentModel = useMemo(() => {
    return authenticatedUser &&
      currentScheme &&
      project?.simplemodel.available[authenticatedUser?.username]?.[currentScheme]
      ? project?.simplemodel.available[authenticatedUser?.username][currentScheme]
      : null;
  }, [project, currentScheme, authenticatedUser]);
  const availableSamples = project?.next.sample ? project?.next.sample : [];
  const availableLabels = useMemo(() => {
    return currentScheme && project ? project.schemes.available[currentScheme] || [] : [];
  }, [project, currentScheme]);
  // available methods depend if there is a simple model trained for the user/scheme
  // TO TEST, and in the future change the API if possible

  const availableModes =
    authenticatedUser &&
    currentScheme &&
    project?.simplemodel.available[authenticatedUser.username]?.[currentScheme]
      ? project.next.methods
      : project?.next.methods_min
        ? project?.next.methods_min
        : [];

  // const elementOutModel = useMemo(() => {
  //   return {
  //     element_id: '',
  //     text: '',
  //     context: {},
  //     selection: '',
  //     info: null,
  //     predict: {},
  //     frame: [],
  //     limit: null,
  //     history: [],
  //   };
  // }, []);

  // const navigateToNextElement = useCallback(async () => {
  //   console.log(selectionConfig);
  //   getNextElementId(selectionConfig).then((nextElementId) => {
  //     if (nextElementId) navigate(`/projects/${projectName}/annotate/${nextElementId}`);
  //     else setElement(elementOutModel);
  //   });
  // }, [projectName, navigate, selectionConfig, getNextElementId, elementOutModel]);

  useEffect(() => {
    if (elementId === undefined) {
      getNextElementId(selectionConfig).then((nextElementId) => {
        if (nextElementId) navigate(`/projects/${projectName}/annotate/${nextElementId}`);
      });
    } else {
      //fetch element information (text and labels)
      getElementById(elementId).then(setElement);
    }
  }, [elementId, getNextElementId, getElementById, navigate, selectionConfig, projectName]);

  // hooks to update simplemodel
  const [updatedSimpleModel, setUpdatedSimpleModel] = useState(false);

  // use a memory to only update once
  const { updateSimpleModel } = useUpdateSimpleModel(projectName || null, currentScheme || null);

  useEffect(() => {
    if (!updatedSimpleModel && currentModel && history.length % freqRefreshSimpleModel == 0) {
      setUpdatedSimpleModel(true);
      updateSimpleModel(currentModel);
    }
    if (updatedSimpleModel && history.length % freqRefreshSimpleModel != 0)
      setUpdatedSimpleModel(false);
    // TODO UPDATE SIMPLEMODEL
  }, [
    history,
    updateSimpleModel,
    setUpdatedSimpleModel,
    currentModel,
    freqRefreshSimpleModel,
    updatedSimpleModel,
  ]);

  // get statistics to display (TODO : try a way to avoid another request ?)
  const { statistics } = useStatistics(projectName || null, currentScheme || null);

  // generic method to apply a chosen label to an element
  const applyLabel = useCallback(
    (label: string, elementId?: string) => {
      if (elementId) {
        setAppContext((prev) => ({ ...prev, history: [...prev.history, elementId] }));
        addAnnotation(elementId, label).then(() =>
          // redirect to next element by redirecting wihout any id
          // thus the getNextElementId query will be dont after the appcontext is reloaded
          navigate(`/projects/${projectName}/annotate/`),
        );
        // does not do nothing as we remount through navigate reFetchStatistics();
      }
    },
    [setAppContext, addAnnotation, navigate, projectName],
  );

  const handleKeyboardEvents = useCallback(
    (ev: KeyboardEvent) => {
      availableLabels.forEach((label, i) => {
        if (ev.code === `Digit` + (i + 1) || ev.code === `Numpad` + (i + 1)) {
          applyLabel(label, elementId);
        }
      });
    },
    [availableLabels, applyLabel, elementId],
  );

  useEffect(() => {
    // manage keyboard shortcut if less than 10 label
    if (availableLabels.length > 0 && availableLabels.length < 10) {
      document.addEventListener('keydown', handleKeyboardEvents);
    }

    return () => {
      if (availableLabels.length > 0 && availableLabels.length < 10) {
        document.removeEventListener('keydown', handleKeyboardEvents);
      }
    };
  }, [availableLabels, handleKeyboardEvents]);

  return (
    <ProjectPageLayout projectName={projectName || null} currentAction="annotate">
      <div className="container-fluid">
        <div className="row">
          <h2 className="subsection">Annotation</h2>

          <Tabs id="panel2" className="mb-3" defaultActiveKey="scheme">
            <Tab eventKey="scheme" title="Current scheme">
              <div className="d-flex">
                <SelectCurrentScheme />
              </div>
              <div>
                {statistics ? (
                  <span className="badge text-bg-light">
                    {`${statistics['annotated_n']} / ${statistics['trainset_n']}`}
                  </span>
                ) : (
                  ''
                )}
              </div>
            </Tab>
            <Tab eventKey="selection" title="Selection mode">
              <div className="d-flex align-items-center justify-content-between">
                <label>Selection mode</label>
                <select
                  className="form-select w-50"
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => {
                    setAppContext((prev) => ({
                      ...prev,
                      selectionConfig: { ...selectionConfig, mode: e.target.value },
                    }));
                  }}
                >
                  {availableModes.map((e, i) => (
                    <option key={i}>{e}</option>
                  ))}
                </select>
              </div>
              {selectionConfig.mode == 'maxprob' && (
                <div>
                  <label>Label</label>
                  <select
                    onChange={(e) => {
                      setAppContext((prev) => ({
                        ...prev,
                        selectionConfig: { ...selectionConfig, label: e.target.value },
                      }));
                    }}
                  >
                    {availableLabels.map((e, i) => (
                      <option key={i}>{e}</option>
                    ))}{' '}
                  </select>
                </div>
              )}
              <div className="d-flex align-items-center justify-content-between">
                <label>On</label>
                <select
                  className="form-select w-50"
                  onChange={(e) => {
                    setAppContext((prev) => ({
                      ...prev,
                      selectionConfig: { ...selectionConfig, sample: e.target.value },
                    }));
                  }}
                >
                  {availableSamples.map((e, i) => (
                    <option key={i}>{e}</option>
                  ))}{' '}
                </select>
              </div>
              <div className="d-flex align-items-center justify-content-between">
                <label htmlFor="select_regex">Filter</label>
                <input
                  className="form-control w-75"
                  type="text"
                  id="select_regex"
                  placeholder="Enter a regex / CONTEXT= for context"
                  onChange={(e) => {
                    setAppContext((prev) => ({
                      ...prev,
                      selectionConfig: { ...selectionConfig, filter: e.target.value },
                    }));
                  }}
                />
              </div>
              <label style={{ display: 'block', marginBottom: '10px' }}>
                <input
                  type="checkbox"
                  checked={selectionConfig.frameSelection}
                  onChange={(_) => {
                    setAppContext((prev) => ({
                      ...prev,
                      selectionConfig: {
                        ...selectionConfig,
                        frameSelection: !selectionConfig.frameSelection,
                      },
                    }));
                    console.log(selectionConfig.frameSelection);
                  }}
                  style={{ marginRight: '10px' }}
                />
                Use zoom frame to select elements
              </label>
              <div>Current model : {currentModel ? currentModel['model'] : 'No model trained'}</div>
            </Tab>
            <Tab eventKey="parameters" title="Display parameters">
              <label style={{ display: 'block', marginBottom: '10px' }}>
                <input
                  type="checkbox"
                  checked={selectionConfig.displayPrediction}
                  onChange={(_) => {
                    setAppContext((prev) => ({
                      ...prev,
                      selectionConfig: {
                        ...selectionConfig,
                        displayPrediction: !selectionConfig.displayPrediction,
                      },
                    }));
                  }}
                  style={{ marginRight: '10px' }}
                />
                Display prediction
              </label>
              <label style={{ display: 'block', marginBottom: '10px' }}>
                <input
                  type="checkbox"
                  checked={selectionConfig.displayContext}
                  onChange={(_) => {
                    setAppContext((prev) => ({
                      ...prev,
                      selectionConfig: {
                        ...selectionConfig,
                        displayContext: !selectionConfig.displayContext,
                      },
                    }));
                  }}
                  style={{ marginRight: '10px' }}
                />
                Display informations
              </label>
            </Tab>
          </Tabs>
        </div>
      </div>

      {
        // back button
      }

      {
        // display content
      }
      <div className="row">
        <div className="col-11 annotation-frame my-4">
          <span>{element?.text.slice(0, element?.limit as number)}</span>
          <span className="text-out-context">{element?.text.slice(element?.limit as number)}</span>
        </div>

        {
          //display proba
          selectionConfig.displayPrediction && (
            <div className="d-flex mb-2 justify-content-center display-prediction">
              Predicted label : {element?.predict.label} (proba: {element?.predict.proba})
            </div>
          )
        }
        {
          //display informations
          selectionConfig.displayContext && (
            <div className="d-flex mb-2 justify-content-center display-prediction">
              Context : {JSON.stringify(element?.context)}
            </div>
          )
        }
      </div>
      <div className="row">
        <div className="d-flex flex-wrap gap-2 justify-content-center">
          <Link
            to={`/projects/${projectName}/annotate/${history[history.length - 1]}`}
            className="btn btn-outline-secondary"
            onClick={() => {
              setAppContext((prev) => ({ ...prev, history: prev.history.slice(0, -1) }));
            }}
          >
            <IoMdReturnLeft />
          </Link>
          {availableLabels.map((i, e) => (
            <button
              type="button"
              key={i}
              value={i}
              className="btn btn-primary grow-1"
              onClick={(e) => {
                applyLabel(e.currentTarget.value, elementId);
              }}
            >
              {i} <span className="badge text-bg-secondary">{e + 1}</span>
            </button>
          ))}
        </div>
      </div>
      <Tabs id="panel2" className="mb-3" defaultActiveKey="description">
        <Tab eventKey="description" title="Parameters">
          Configure the annotation
        </Tab>
        <Tab eventKey="labels" title="Labels">
          <LabelsManagement
            projectName={projectName || null}
            currentScheme={currentScheme || null}
            availableLabels={availableLabels}
            reFetchCurrentProject={reFetchCurrentProject || (() => null)}
          />
        </Tab>
        <Tab eventKey="prediction" title="Prediction">
          <SimpleModelManagement
            projectName={projectName || null}
            currentScheme={currentScheme || null}
            availableSimpleModels={availableSimpleModels}
            availableFeatures={availableFeatures}
          />
        </Tab>
        <Tab eventKey="projection" title="Projection">
          <ProjectionManagement />
        </Tab>
      </Tabs>
    </ProjectPageLayout>
  );
};
